"""Core PDF Personalization and Replacement Engine for DocMorph.

Coordinates precision redaction and text replacement:
- Validates replacement requests and confirmed field statuses.
- Analyzes typography and layout constraints.
- Applies localized PyMuPDF redaction annotations (images & line art preserved).
- Inserts replacement text at exact baseline coordinates with adaptive font scaling.
- Guarantees original PDF immutability by outputting to a separate unique file.
- Executes independent post-generation output verification.
"""

from collections import defaultdict
import hashlib
from pathlib import Path
import re
import time
from typing import Any, Optional
import uuid
import pymupdf

from app.core.config import Settings, settings
from app.core.exceptions import (
    DocMorphError,
    OutputVerificationError,
    PDFProcessingError,
    PDFReplacementError,
    PDFValidationError,
)
from app.schemas.detection_data import (
    BoundingBox,
    DetectionResult,
    FieldOccurrence,
    FieldType,
)
from app.schemas.replacement_data import (
    ReplacementItem,
    ReplacementOccurrenceResult,
    ReplacementRequest,
    ReplacementResult,
    ReplacementStatus,
    VerificationStatus,
)
from app.services.formatting_analyzer import FormattingAnalyzer
from app.services.output_verifier import OutputVerifier
from app.services.replacement_validator import ReplacementValidator
from app.utils.file_validator import FileValidator


class PDFReplacer:
    """Production-grade text replacement and PDF personalization engine."""

    def __init__(self, config: Settings = settings) -> None:
        """Initialize replacement engine with modular analyzer, validator, and verifier.

        Args:
            config: Application configuration instance.
        """
        self.config = config
        self.validator = ReplacementValidator(config=config)
        self.formatter = FormattingAnalyzer(config=config)
        self.verifier = OutputVerifier()

    def replace_fields(
        self,
        source_pdf: Path | str,
        detection_result: DetectionResult,
        request: ReplacementRequest,
        output_dir: Optional[Path] = None,
    ) -> ReplacementResult:
        """Personalizes confirmed student fields in a PDF, generating a verified output file.

        Args:
            source_pdf: Path to the original input PDF document.
            detection_result: Trusted Phase 2 detection results containing occurrences.
            request: Client replacement request containing target fields and new values.
            output_dir: Optional destination directory; defaults to config.OUTPUT_DIR.

        Returns:
            ReplacementResult containing execution summary, per-occurrence logs, and verification.

        Raises:
            UnconfirmedFieldError: If target fields are unconfirmed or rejected.
            InvalidReplacementRequestError: If input values or formats are invalid.
            PDFReplacementError: If rendering or redaction fails.
        """
        start_time = time.perf_counter()

        # Step 1: Validate input PDF and request
        resolved_source = FileValidator.validate_file_path(source_pdf, config=self.config)
        self.validator.validate_request(request, detection_result)

        # Step 2: Record original file hash for immutability verification
        original_hash = self._compute_file_sha256(resolved_source)

        # Step 3: Determine safe output destination
        job_id = f"job_{uuid.uuid4().hex[:8]}"
        target_dir = Path(output_dir) if output_dir else self.config.OUTPUT_DIR
        target_dir.mkdir(parents=True, exist_ok=True)

        safe_filename = request.output_filename or (
            f"personalized_{resolved_source.stem}_{job_id[4:]}.pdf"
        )
        # Ensure output filename is sanitized and ends with .pdf
        clean_output_name = FileValidator.sanitize_filename(safe_filename)
        output_path = target_dir / clean_output_name

        # Ensure we never overwrite the original input PDF
        if output_path.resolve() == resolved_source.resolve():
            output_path = target_dir / f"copy_{clean_output_name}"

        occurrence_results: list[ReplacementOccurrenceResult] = []
        all_warnings: list[str] = []

        try:
            # Step 4: Open document in PyMuPDF
            with pymupdf.open(str(resolved_source)) as doc:
                expected_page_count = doc.page_count

                # Organize replacement items by page number
                # Mapping: page_num -> list of (ReplacementItem, FieldOccurrence)
                page_tasks: dict[int, list[tuple[ReplacementItem, FieldOccurrence]]] = (
                    defaultdict(list)
                )

                for item in request.replacements:
                    detected_field = detection_result.get_field(item.field_id)
                    if not detected_field:
                        continue
                    for occ in detected_field.occurrences:
                        page_tasks[occ.page_number].append((item, occ))

                # Step 5: Execute replacements page-by-page
                for page_num, tasks in page_tasks.items():
                    if page_num > expected_page_count:
                        continue

                    page = doc[page_num - 1]

                    # 5a. Partition tasks on this page into paired identity tasks and single tasks
                    paired_groups: list[dict[str, Any]] = []
                    used_indices: set[int] = set()

                    id_types = (
                        FieldType.ENROLLMENT_NUMBER,
                        FieldType.ROLL_NUMBER,
                        FieldType.STUDENT_ID,
                        FieldType.UNKNOWN_IDENTIFIER,
                    )

                    # Check for pairs among requested tasks
                    for i in range(len(tasks)):
                        if i in used_indices:
                            continue
                        item_a, occ_a = tasks[i]
                        for j in range(i + 1, len(tasks)):
                            if j in used_indices:
                                continue
                            item_b, occ_b = tasks[j]

                            is_name_a = item_a.field_type == FieldType.STUDENT_NAME
                            is_name_b = item_b.field_type == FieldType.STUDENT_NAME
                            is_id_a = item_a.field_type in id_types
                            is_id_b = item_b.field_type in id_types

                            if (is_name_a and is_id_b) or (is_name_b and is_id_a):
                                name_task = (item_a, occ_a) if is_name_a else (item_b, occ_b)
                                id_task = (item_b, occ_b) if is_name_a else (item_a, occ_a)

                                n_occ, i_occ = name_task[1], id_task[1]
                                is_unlabelled_pair = not n_occ.matched_label and not i_occ.matched_label
                                same_pair_id = bool(n_occ.pair_id and n_occ.pair_id == i_occ.pair_id)
                                same_raw = bool(
                                    n_occ.raw_text
                                    and i_occ.raw_text
                                    and n_occ.raw_text.strip() == i_occ.raw_text.strip()
                                )
                                same_y = (
                                    (
                                        n_occ.is_in_footer_region
                                        or i_occ.is_in_footer_region
                                        or n_occ.bbox.y0 > page.rect.height * 0.55
                                    )
                                    and abs(n_occ.bbox.y0 - i_occ.bbox.y0) <= 4.0
                                )

                                # Only unify unlabelled identity pairs (labeled fields retain individual replacement)
                                if same_pair_id or (is_unlabelled_pair and (same_raw or same_y)):
                                    paired_groups.append({
                                        "name_item": name_task[0],
                                        "name_occ": name_task[1],
                                        "id_item": id_task[0],
                                        "id_occ": id_task[1],
                                        "is_name_requested": True,
                                        "is_id_requested": True,
                                    })
                                    used_indices.add(i)
                                    used_indices.add(j)
                                    break

                    # Check remaining tasks: does any single task have an unrequested partner in detection_result?
                    single_tasks: list[tuple[ReplacementItem, FieldOccurrence]] = []
                    for k in range(len(tasks)):
                        if k in used_indices:
                            continue
                        item_k, occ_k = tasks[k]

                        # Labeled fields are always replaced individually
                        if occ_k.matched_label:
                            single_tasks.append((item_k, occ_k))
                            continue

                        partner_found = False
                        is_name = item_k.field_type == FieldType.STUDENT_NAME
                        target_partner_types = id_types if is_name else (FieldType.STUDENT_NAME,)

                        for other_field in detection_result.detected_fields:
                            if other_field.field_type not in target_partner_types:
                                continue
                            for other_occ in other_field.occurrences:
                                if other_occ.page_number != page_num or other_occ.matched_label:
                                    continue
                                same_p = bool(occ_k.pair_id and occ_k.pair_id == other_occ.pair_id)
                                same_r = bool(
                                    occ_k.raw_text
                                    and other_occ.raw_text
                                    and occ_k.raw_text.strip() == other_occ.raw_text.strip()
                                )
                                same_y = (
                                    (
                                        occ_k.is_in_footer_region
                                        or other_occ.is_in_footer_region
                                        or occ_k.bbox.y0 > page.rect.height * 0.55
                                    )
                                    and abs(occ_k.bbox.y0 - other_occ.bbox.y0) <= 4.0
                                )
                                if same_p or same_r or same_y:
                                    dummy_partner_item = ReplacementItem(
                                        field_id=other_field.field_id,
                                        field_type=other_field.field_type,
                                        original_value=other_field.original_value,
                                        new_value=other_field.original_value,
                                    )
                                    if is_name:
                                        paired_groups.append({
                                            "name_item": item_k,
                                            "name_occ": occ_k,
                                            "id_item": dummy_partner_item,
                                            "id_occ": other_occ,
                                            "is_name_requested": True,
                                            "is_id_requested": False,
                                        })
                                    else:
                                        paired_groups.append({
                                            "name_item": dummy_partner_item,
                                            "name_occ": other_occ,
                                            "id_item": item_k,
                                            "id_occ": occ_k,
                                            "is_name_requested": False,
                                            "is_id_requested": True,
                                        })
                                    partner_found = True
                                    used_indices.add(k)
                                    break
                            if partner_found:
                                break

                        if not partner_found:
                            single_tasks.append((item_k, occ_k))

                    # 5b. Stage paired insertions
                    staged_paired_insertions: list[dict[str, Any]] = []
                    for pg in paired_groups:
                        name_item = pg["name_item"]
                        name_occ = pg["name_occ"]
                        id_item = pg["id_item"]
                        id_occ = pg["id_occ"]

                        is_inverted = id_occ.bbox.x0 < name_occ.bbox.x0
                        raw_line_text = name_occ.raw_text or id_occ.raw_text or ""
                        unified_text = self._build_unified_replacement_text(
                            raw_line_text, name_item.new_value, id_item.new_value, is_inverted
                        )

                        line_rect, line_origin, span_font, span_size = self._find_line_geometry(
                            page, name_occ, id_occ
                        )

                        if line_origin is not None:
                            effective_font = self.formatter.map_font_name(span_font or "TimesNewRomanPSMT")
                            effective_size = span_size or 11.0
                            baseline_y = line_origin.y
                            color_rgb = (0, 0, 0)
                        else:
                            fmt = self.formatter.analyze_occurrence(
                                page=page, occurrence=name_occ, target_value=name_item.original_value
                            )
                            effective_font = fmt.font_name
                            effective_size = fmt.font_size
                            baseline_y = fmt.origin[1]
                            color_rgb = fmt.color_rgb

                        origin_pt = pymupdf.Point(line_rect.x0, baseline_y)

                        available_w = max(line_rect.width, (page.rect.width * 0.50) - line_rect.x0)
                        fitted_size, has_collision, warning_msg = (
                            self.formatter.calculate_fitted_font_size(
                                text=unified_text,
                                font_name=effective_font,
                                base_font_size=effective_size,
                                available_width=available_w,
                            )
                        )
                        if warning_msg:
                            all_warnings.append(f"Page {page_num} (unified): {warning_msg}")

                        # Redact the unified rectangle covering the entire identity line
                        page.add_redact_annot(line_rect, fill=(1, 1, 1))

                        staged_paired_insertions.append({
                            "group": pg,
                            "unified_text": unified_text,
                            "line_rect": line_rect,
                            "origin_pt": origin_pt,
                            "effective_font": effective_font,
                            "fitted_size": fitted_size,
                            "color_rgb": color_rgb,
                            "warning_msg": warning_msg,
                        })

                    # 5c. Stage single insertions
                    staged_insertions = []
                    for item, occ in single_tasks:
                        val_bbox = occ.value_bbox or occ.bbox
                        val_rect = pymupdf.Rect(val_bbox.to_tuple())

                        fmt = self.formatter.analyze_occurrence(
                            page=page,
                            occurrence=occ,
                            target_value=item.original_value,
                        )

                        fitted_size, has_collision, warning_msg = (
                            self.formatter.calculate_fitted_font_size(
                                text=item.new_value,
                                font_name=fmt.font_name,
                                base_font_size=fmt.font_size,
                                available_width=fmt.available_width,
                            )
                        )

                        if warning_msg:
                            all_warnings.append(f"Page {page_num} ({item.field_id}): {warning_msg}")

                        if has_collision:
                            occurrence_results.append(
                                ReplacementOccurrenceResult(
                                    page_number=page_num,
                                    field_id=item.field_id,
                                    status=ReplacementStatus.FAILED,
                                    message=warning_msg or "Text collision detected",
                                    warning=warning_msg,
                                    original_bbox=val_bbox,
                                    new_bbox=None,
                                    original_value=item.original_value,
                                    inserted_value="",
                                )
                            )
                            continue

                        page.add_redact_annot(val_rect, fill=(1, 1, 1))
                        staged_insertions.append(
                            (item, occ, fmt, fitted_size, val_rect, warning_msg)
                        )

                    # 5d. Apply all redactions in batch for this page
                    page.apply_redactions(images=0, graphics=0, text=0)

                    # 5e. Insert unified identity lines
                    for spi in staged_paired_insertions:
                        font_to_use = self.formatter.normalize_base_font(spi["effective_font"])
                        try:
                            page.insert_text(
                                spi["origin_pt"],
                                spi["unified_text"],
                                fontname=font_to_use,
                                fontsize=spi["fitted_size"],
                                color=spi["color_rgb"],
                            )
                        except Exception:
                            font_to_use = "tiro" if "ti" in font_to_use else "helv"
                            page.insert_text(
                                spi["origin_pt"],
                                spi["unified_text"],
                                fontname=font_to_use,
                                fontsize=spi["fitted_size"],
                                color=spi["color_rgb"],
                            )

                        try:
                            new_text_w = pymupdf.get_text_length(
                                spi["unified_text"], fontname=font_to_use, fontsize=spi["fitted_size"]
                            )
                        except Exception:
                            new_text_w = pymupdf.get_text_length(
                                spi["unified_text"], fontname="helv", fontsize=spi["fitted_size"]
                            )

                        new_bbox = BoundingBox(
                            x0=round(spi["line_rect"].x0, 2),
                            y0=round(spi["line_rect"].y0, 2),
                            x1=round(spi["line_rect"].x0 + new_text_w, 2),
                            y1=round(spi["line_rect"].y1, 2),
                        )

                        grp = spi["group"]
                        warn = spi["warning_msg"]
                        stat = ReplacementStatus.WARNING if warn else ReplacementStatus.SUCCESS

                        if grp["is_name_requested"]:
                            occurrence_results.append(
                                ReplacementOccurrenceResult(
                                    page_number=page_num,
                                    field_id=grp["name_item"].field_id,
                                    status=stat,
                                    message="Personalized successfully (unified alignment)",
                                    warning=warn,
                                    original_bbox=grp["name_occ"].value_bbox or grp["name_occ"].bbox,
                                    new_bbox=new_bbox,
                                    original_value=grp["name_item"].original_value,
                                    inserted_value=grp["name_item"].new_value,
                                )
                            )
                        if grp["is_id_requested"]:
                            occurrence_results.append(
                                ReplacementOccurrenceResult(
                                    page_number=page_num,
                                    field_id=grp["id_item"].field_id,
                                    status=stat,
                                    message="Personalized successfully (unified alignment)",
                                    warning=warn,
                                    original_bbox=grp["id_occ"].value_bbox or grp["id_occ"].bbox,
                                    new_bbox=new_bbox,
                                    original_value=grp["id_item"].original_value,
                                    inserted_value=grp["id_item"].new_value,
                                )
                            )

                    # 5f. Insert single field replacements
                    for item, occ, fmt, fitted_size, val_rect, warning_msg in staged_insertions:
                        origin_pt = pymupdf.Point(val_rect.x0, fmt.origin[1])
                        effective_font = self.formatter.normalize_base_font(fmt.font_name)
                        try:
                            page.insert_text(
                                origin_pt,
                                item.new_value,
                                fontname=effective_font,
                                fontsize=fitted_size,
                                color=fmt.color_rgb,
                            )
                        except Exception:
                            effective_font = "tiro" if "ti" in effective_font else "helv"
                            page.insert_text(
                                origin_pt,
                                item.new_value,
                                fontname=effective_font,
                                fontsize=fitted_size,
                                color=fmt.color_rgb,
                            )

                        try:
                            new_text_w = pymupdf.get_text_length(
                                item.new_value, fontname=effective_font, fontsize=fitted_size
                            )
                        except Exception:
                            new_text_w = pymupdf.get_text_length(
                                item.new_value, fontname="helv", fontsize=fitted_size
                            )
                        new_bbox = BoundingBox(
                            x0=val_rect.x0,
                            y0=val_rect.y0,
                            x1=round(val_rect.x0 + new_text_w, 2),
                            y1=val_rect.y1,
                        )

                        occ_status = (
                            ReplacementStatus.WARNING
                            if warning_msg
                            else ReplacementStatus.SUCCESS
                        )
                        occurrence_results.append(
                            ReplacementOccurrenceResult(
                                page_number=page_num,
                                field_id=item.field_id,
                                status=occ_status,
                                message="Personalized successfully",
                                warning=warning_msg,
                                original_bbox=occ.value_bbox or occ.bbox,
                                new_bbox=new_bbox,
                                original_value=item.original_value,
                                inserted_value=item.new_value,
                            )
                        )

                # Step 6: Save personalized PDF to output path
                doc.save(str(output_path), garbage=3, deflate=True)

            # Step 7: Verify original PDF remained unchanged
            post_hash = self._compute_file_sha256(resolved_source)
            if post_hash != original_hash:
                raise PDFReplacementError("CRITICAL: Original PDF was modified during personalization!")

            # Step 8: Independent Output Verification
            verification_rep = self.verifier.verify_output(
                output_pdf_path=output_path,
                expected_page_count=expected_page_count,
                replacements=request.replacements,
                detection_result=detection_result,
                occurrence_results=occurrence_results,
            )

            if not verification_rep.passed:
                all_warnings.extend(verification_rep.errors)

            # Compute execution totals
            total_req = len(request.replacements)
            successful_field_ids = {
                r.field_id
                for r in occurrence_results
                if r.status in (ReplacementStatus.SUCCESS, ReplacementStatus.WARNING)
            }
            total_succ = len(successful_field_ids)
            total_fail = total_req - total_succ

            total_occ = len(occurrence_results)
            succ_occ = sum(
                1
                for r in occurrence_results
                if r.status in (ReplacementStatus.SUCCESS, ReplacementStatus.WARNING)
            )
            fail_occ = total_occ - succ_occ

            duration = time.perf_counter() - start_time

            return ReplacementResult(
                job_id=job_id,
                original_filename=resolved_source.name,
                output_filename=clean_output_name,
                output_path=str(output_path),
                total_requested=total_req,
                total_successful=total_succ,
                total_failed=total_fail,
                total_occurrences=total_occ,
                successful_occurrences=succ_occ,
                failed_occurrences=fail_occ,
                warnings=all_warnings,
                processing_duration_seconds=round(duration, 4),
                processing_duration_formatted=f"{duration:.4f}s",
                verification_status=verification_rep.status,
                occurrence_results=occurrence_results,
            )

        except (DocMorphError, PDFValidationError):
            raise
        except Exception as e:
            raise PDFReplacementError(
                f"Personalization engine failure: {type(e).__name__} - {e}"
            ) from e

    @staticmethod
    def _compute_file_sha256(file_path: Path) -> str:
        """Computes SHA-256 hash of a file for integrity verification."""
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _build_unified_replacement_text(
        raw_text: str,
        name_val: str,
        id_val: str,
        is_inverted: bool = False,
    ) -> str:
        """Builds a unified identity line preserving original punctuation and delimiters."""
        clean_raw = raw_text.strip() if raw_text else ""

        # Parentheses or brackets: e.g. 'Vivek dhedhi (92400120571)' or 'VivekDhedhi(92400120571)'
        if re.search(r"[\(\[]\s*.*?\s*[\)\]]", clean_raw):
            if is_inverted:
                return f"({id_val}) {name_val}"
            return f"{name_val} ({id_val})"

        # Delimiter hyphens / dashes: e.g. 'Vivek Dhedhi - 92400120571'
        if re.search(r"\s*[\-–—]\s*", clean_raw):
            sep = " - "
            return f"{id_val}{sep}{name_val}" if is_inverted else f"{name_val}{sep}{id_val}"

        # Pipe delimiter: e.g. 'Vivek Dhedhi | 92400120571'
        if "|" in clean_raw:
            return f"{id_val} | {name_val}" if is_inverted else f"{name_val} | {id_val}"

        # Comma delimiter: e.g. 'Vivek Dhedhi, 92400120571'
        if "," in clean_raw:
            return f"{id_val}, {name_val}" if is_inverted else f"{name_val}, {id_val}"

        # Default standard spacing
        return f"({id_val}) {name_val}" if is_inverted else f"{name_val} ({id_val})"

    @staticmethod
    def _find_line_geometry(
        page: pymupdf.Page,
        name_occ: FieldOccurrence,
        id_occ: FieldOccurrence,
    ) -> tuple[pymupdf.Rect, Optional[pymupdf.Point], Optional[str], Optional[float]]:
        """Locates the precise enclosing line bounding box, origin, and font from the PyMuPDF page dictionary."""
        val_box_n = name_occ.value_bbox or name_occ.bbox
        val_box_i = id_occ.value_bbox or id_occ.bbox
        target_y = min(val_box_n.y0, val_box_i.y0)
        target_x = min(val_box_n.x0, val_box_i.x0)
        clean_raw = (name_occ.raw_text or id_occ.raw_text or "").strip()

        for block in page.get_text("dict").get("blocks", []):
            if block.get("type") == 0:
                for line in block.get("lines", []):
                    line_text = "".join(s.get("text", "") for s in line.get("spans", [])).strip()
                    lr = pymupdf.Rect(line["bbox"])
                    if line_text and abs(lr.y0 - target_y) <= 5.0:
                        if (
                            clean_raw in line_text
                            or (len(line_text) >= 5 and line_text in clean_raw)
                        ) and abs(lr.x0 - target_x) <= 8.0:
                            s0 = line["spans"][0]
                            orig = pymupdf.Point(lr.x0, s0["origin"][1]) if "origin" in s0 else None
                            return lr, orig, s0.get("font"), s0.get("size")

        # Fallback to union of occurrences
        x0 = min(val_box_n.x0, val_box_i.x0)
        y0 = min(val_box_n.y0, val_box_i.y0)
        x1 = max(val_box_n.x1, val_box_i.x1)
        y1 = max(val_box_n.y1, val_box_i.y1)
        if name_occ.line_bbox:
            x0 = min(x0, name_occ.line_bbox.x0)
            x1 = max(x1, name_occ.line_bbox.x1)
        if id_occ.line_bbox:
            x0 = min(x0, id_occ.line_bbox.x0)
            x1 = max(x1, id_occ.line_bbox.x1)
        return pymupdf.Rect(x0, y0, x1, y1), None, None, None

