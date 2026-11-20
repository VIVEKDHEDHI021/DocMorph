"""Footer Verification Layer for DocMorph.

Decouples footer existence verification from student-information detection.
Evaluates independent layout, multi-page, semantic, and negative evidence
to classify documents into one of four canonical states:
- FOOTER_CONFIRMED
- FOOTER_NOT_FOUND
- FOOTER_UNCERTAIN
- DOCUMENT_UNREADABLE
"""

import re
from typing import Optional
import pymupdf

from app.schemas.detection_data import BoundingBox
from app.schemas.footer_verification import (
    DocumentFooterVerification,
    FooterEvidenceScores,
    FooterStatus,
    PageFooterVerification,
)
from app.services.footer_detector import FooterDetector
from app.services.text_segmenter import StructuredLine


class FooterVerifier:
    """Production-grade multi-signal verification layer for PDF document footers."""

    # Explicit negative markers that indicate ordinary body, chapter, experiment, or syllabus text
    NEGATIVE_KEYWORDS = [
        "conclusion", "conclusions", "result", "results", "observation", "observations",
        "apparatus", "theory", "procedure", "precaution", "precautions",
        "experiment", "practical", "exercise", "assignment", "problem", "solution",
        "chapter", "section", "unit", "module", "topic", "index",
        "reference", "references", "bibliography", "citation", "citations",
        "department", "faculty", "university", "institute", "college",
        "author", "edition", "published", "publisher", "isbn", "issn",
        "syllabus", "curriculum", "aim", "objective", "discussion",
        "figure", "fig.", "table", "chart", "diagram", "graph",
        "algorithm", "code", "output", "program", "source code",
        "course", "subject", "signature", "remark", "grade", "assessment",
    ]

    # Regex patterns for negative triggers
    RE_EXP_CHAPTER = re.compile(
        r"(?i)\b(?:experiment|exp\.?|practical|chapter|unit|section|exercise)\s*(?:no\.?|#)?\s*\d+",
        re.IGNORECASE,
    )
    RE_SOLITARY_PAGE_NUMBER = re.compile(
        r"(?i)^(?:page\s*\d+(\s*of\s*\d+)?|\d+\s*/\s*\d+|[-–—]\s*\d+\s*[-–—]|\d{1,3})$"
    )
    RE_PROSE_INDICATORS = re.compile(
        r"\b(?:the|this|that|which|these|those|with|from|between|because|therefore|however|where|when|should|would|could)\b",
        re.IGNORECASE,
    )

    def __init__(self, footer_detector: Optional[FooterDetector] = None) -> None:
        self.footer_detector = footer_detector or FooterDetector()

    def verify_document(
        self,
        doc: pymupdf.Document,
        structured_pages: dict[int, list[StructuredLine]],
    ) -> DocumentFooterVerification:
        """Evaluates document-wide footer evidence across all pages.

        Args:
            doc: Open PyMuPDF Document instance.
            structured_pages: Mapping of 1-based page numbers to their segmented lines.

        Returns:
            DocumentFooterVerification with page-level and document-level determinations.
        """
        try:
            total_pages = doc.page_count
        except Exception:
            return DocumentFooterVerification(
                status=FooterStatus.DOCUMENT_UNREADABLE,
                confidence=0.0,
                total_pages=0,
                summary_message="The document could not be read or parsed.",
            )

        if total_pages == 0:
            return DocumentFooterVerification(
                status=FooterStatus.DOCUMENT_UNREADABLE,
                confidence=0.0,
                total_pages=0,
                summary_message="The document has zero pages.",
            )

        # 1. Page-level preliminary evaluations
        page_prelims: list[dict] = []
        for page_idx in range(1, total_pages + 1):
            try:
                page = doc[page_idx - 1]
                lines = structured_pages.get(page_idx, [])
                prelim = self._analyze_page_evidence(page, page_idx, lines)
                page_prelims.append(prelim)
            except Exception as e:
                page_prelims.append({
                    "page_number": page_idx,
                    "status": FooterStatus.DOCUMENT_UNREADABLE,
                    "confidence": 0.0,
                    "error": str(e),
                })

        # 2. Multi-page cross-page evidence aggregation
        multi_page_bonus_map = self._compute_multi_page_consistency(page_prelims, total_pages)

        # 3. Finalize per-page classifications with multi-page bonuses
        final_page_results: list[PageFooterVerification] = []
        confirmed_count = 0
        uncertain_count = 0
        not_found_count = 0

        for prelim in page_prelims:
            if prelim.get("status") == FooterStatus.DOCUMENT_UNREADABLE:
                final_page_results.append(
                    PageFooterVerification(
                        page_number=prelim["page_number"],
                        status=FooterStatus.DOCUMENT_UNREADABLE,
                        confidence=0.0,
                        boundary_y=0.0,
                        negative_reasons=[prelim.get("error", "Unreadable page")],
                    )
                )
                continue

            page_num = prelim["page_number"]
            mp_bonus = multi_page_bonus_map.get(page_num, 0.0)

            # Update scores with multi-page evidence
            layout_score = prelim["layout_score"]
            semantic_score = prelim["semantic_score"]
            negative_score = prelim["negative_score"]
            raw_multi_page = prelim["multi_page_score"] + mp_bonus

            net_score = (layout_score + raw_multi_page + semantic_score) - negative_score

            has_id_pair = prelim.get("has_id_pair", False)
            has_explicit_labels = prelim.get("has_explicit_labels", False)

            # Decide page status
            if has_id_pair or has_explicit_labels:
                page_status = FooterStatus.FOOTER_CONFIRMED if net_score >= 35.0 else FooterStatus.FOOTER_UNCERTAIN
                confidence = min(0.98, max(0.75, (net_score / 100.0)))
            elif negative_score >= 40.0:
                page_status = FooterStatus.FOOTER_NOT_FOUND
                confidence = max(0.80, min(0.99, negative_score / 100.0))
            elif net_score >= 50.0 and layout_score >= 20.0:
                page_status = FooterStatus.FOOTER_CONFIRMED
                confidence = min(0.98, max(0.70, (net_score / 100.0)))
            elif net_score >= 20.0 and negative_score < 30.0:
                page_status = FooterStatus.FOOTER_UNCERTAIN
                confidence = 0.50
            else:
                page_status = FooterStatus.FOOTER_NOT_FOUND
                confidence = max(0.75, 1.0 - max(0.0, net_score) / 100.0)

            if page_status == FooterStatus.FOOTER_CONFIRMED:
                confirmed_count += 1
            elif page_status == FooterStatus.FOOTER_UNCERTAIN:
                uncertain_count += 1
            else:
                not_found_count += 1

            evidence_scores = FooterEvidenceScores(
                layout_score=round(layout_score, 1),
                multi_page_score=round(raw_multi_page, 1),
                semantic_score=round(semantic_score, 1),
                negative_score=round(negative_score, 1),
                total_score=round(net_score, 1),
            )

            final_page_results.append(
                PageFooterVerification(
                    page_number=page_num,
                    status=page_status,
                    confidence=round(confidence, 3),
                    boundary_y=round(prelim["boundary_y"], 2),
                    has_separator_line=prelim["has_separator_line"],
                    separator_y=prelim["separator_y"],
                    footer_bbox=prelim["footer_bbox"],
                    evidence=evidence_scores,
                    negative_reasons=prelim["negative_reasons"],
                    candidate_texts=prelim["candidate_texts"],
                )
            )

        # 4. Synthesize document-level determination
        doc_status: FooterStatus
        doc_confidence: float
        summary_msg: str

        if any(p.status == FooterStatus.DOCUMENT_UNREADABLE for p in final_page_results):
            doc_status = FooterStatus.DOCUMENT_UNREADABLE
            doc_confidence = 0.0
            summary_msg = "One or more pages could not be read or parsed."
        elif confirmed_count >= 1:
            doc_status = FooterStatus.FOOTER_CONFIRMED
            doc_confidence = round(
                sum(p.confidence for p in final_page_results if p.status == FooterStatus.FOOTER_CONFIRMED)
                / confirmed_count,
                3,
            )
            summary_msg = f"A recognizable footer was confirmed on {confirmed_count} of {total_pages} page(s)."
        elif uncertain_count >= 1:
            doc_status = FooterStatus.FOOTER_UNCERTAIN
            doc_confidence = 0.50
            summary_msg = "Footer candidates exist but confidence is insufficient for automatic personalization."
        else:
            doc_status = FooterStatus.FOOTER_NOT_FOUND
            doc_confidence = 0.90
            summary_msg = "This document does not appear to contain a recognizable footer."

        return DocumentFooterVerification(
            status=doc_status,
            confidence=doc_confidence,
            total_pages=total_pages,
            confirmed_pages_count=confirmed_count,
            uncertain_pages_count=uncertain_count,
            not_found_pages_count=not_found_count,
            page_results=final_page_results,
            summary_message=summary_msg,
        )

    def _analyze_page_evidence(
        self,
        page: pymupdf.Page,
        page_number: int,
        lines: list[StructuredLine],
    ) -> dict:
        """Evaluates layout, negative, and semantic signals on a single page."""
        page_height = page.rect.height
        page_width = page.rect.width

        # Check for vector separator line in lower 40% of page
        separator_y = self.footer_detector.find_footer_separator_line(page)
        has_separator = separator_y is not None

        # Determine lower candidate threshold: 72% height (or separator_y if present)
        lower_threshold = separator_y if separator_y is not None else (page_height * 0.72)

        # Partition lines into body candidates vs footer candidates
        body_lines: list[StructuredLine] = []
        footer_candidates: list[StructuredLine] = []

        for line in lines:
            mid_y = (line.bbox.y0 + line.bbox.y1) / 2.0
            if mid_y >= lower_threshold:
                footer_candidates.append(line)
            else:
                body_lines.append(line)

        # Baseline: If no text exists in the bottom zone at all
        if not footer_candidates:
            return {
                "page_number": page_number,
                "status": FooterStatus.FOOTER_NOT_FOUND,
                "layout_score": 0.0,
                "multi_page_score": 0.0,
                "semantic_score": 0.0,
                "negative_score": 0.0,
                "boundary_y": page_height,
                "has_separator_line": has_separator,
                "separator_y": separator_y,
                "footer_bbox": None,
                "negative_reasons": ["No text in lower page region"],
                "candidate_texts": [],
            }

        layout_score = 0.0
        semantic_score = 0.0
        negative_score = 0.0
        negative_reasons: list[str] = []

        candidate_texts = [l.text.strip() for l in footer_candidates if l.text.strip()]
        combined_footer_text = " ".join(candidate_texts)

        # --- A. NEGATIVE EVIDENCE EVALUATION ---
        for line in footer_candidates:
            text = line.text.strip()
            lower_text = text.lower()

            # 1. Negative academic keywords
            for kw in self.NEGATIVE_KEYWORDS:
                # Word boundary match
                if re.search(r"\b" + re.escape(kw) + r"\b", lower_text):
                    negative_score += 35.0
                    negative_reasons.append(f"Contains negative body keyword '{kw}'")
                    break

            # 2. Experiment / Chapter / Unit numbers
            if self.RE_EXP_CHAPTER.search(text):
                negative_score += 40.0
                negative_reasons.append(f"Contains experiment/chapter pattern: '{text[:30]}'")

            # 3. Prose / running paragraph indicators
            prose_matches = self.RE_PROSE_INDICATORS.findall(text)
            if len(prose_matches) >= 3 or (len(text.split()) > 12 and text.endswith(".")):
                negative_score += 35.0
                negative_reasons.append(f"Prose-like running sentence structure ({len(prose_matches)} prose words)")

        # 4. Check for solitary page number without any student credentials
        if len(footer_candidates) == 1 and self.RE_SOLITARY_PAGE_NUMBER.match(candidate_texts[0]):
            negative_score += 45.0
            negative_reasons.append("Solitary page number alone (not a student footer)")

        # 5. Body Text Continuation (lack of vertical separation)
        if body_lines:
            lowest_body_y = max(l.bbox.y1 for l in body_lines)
            highest_footer_y = min(l.bbox.y0 for l in footer_candidates)
            gap = highest_footer_y - lowest_body_y

            if not has_separator:
                if gap < 16.0:
                    # Line spacing is ordinary paragraph spacing (< 16pt)
                    negative_score += 35.0
                    negative_reasons.append(f"No vertical separation from body text (gap={gap:.1f}pt)")
                elif gap >= 28.0:
                    layout_score += 25.0
                elif gap >= 18.0:
                    layout_score += 15.0
        else:
            # Standalone page with only footer-like elements
            layout_score += 10.0

        # --- B. LAYOUT EVIDENCE EVALUATION ---
        if has_separator:
            layout_score += 40.0

        # Footer compactness: footers are usually 1 or 2 lines
        if 1 <= len(footer_candidates) <= 2:
            layout_score += 20.0
        elif len(footer_candidates) >= 5:
            negative_score += 25.0
            negative_reasons.append(f"Too many lines in footer zone ({len(footer_candidates)} lines)")

        # Proximity to bottom margin
        first_cand_y0 = min(l.bbox.y0 for l in footer_candidates)
        if first_cand_y0 >= page_height * 0.85:
            layout_score += 20.0
        elif first_cand_y0 >= page_height * 0.78:
            layout_score += 10.0

        # Compute footer bounding box
        f_x0 = min(l.bbox.x0 for l in footer_candidates)
        f_y0 = min(l.bbox.y0 for l in footer_candidates)
        f_x1 = max(l.bbox.x1 for l in footer_candidates)
        f_y1 = max(l.bbox.y1 for l in footer_candidates)
        footer_bbox = BoundingBox(x0=f_x0, y0=f_y0, x1=f_x1, y1=f_y1)

        # --- C. SEMANTIC EVIDENCE (SUPPORTING ONLY) ---
        # Look for student name / enrollment number / roll number patterns
        # 1. Identity pair pattern: Name (Enrollment) or Name - Enrollment
        has_id_pair = bool(
            re.search(r"([A-Za-z\s.'-]{3,35})\s*[\(\[]\s*(\d{6,18}|[A-Za-z0-9\-_]{5,20})\s*[\)\]]", combined_footer_text)
            or re.search(r"([A-Za-z\s.'-]{3,35})\s*[-–—|]\s*(\d{6,18})", combined_footer_text)
        )
        if has_id_pair:
            semantic_score += 45.0
            negative_score = max(0.0, negative_score - 30.0)

        # 2. Explicit label markers: "Name:", "Enrollment:", "Roll No:"
        has_explicit_labels = bool(
            re.search(r"(?i)\b(?:name|enrollment(?:\s*no\.?)?|roll(?:\s*no\.?)?|student\s*id)\s*:", combined_footer_text)
        )
        if has_explicit_labels:
            semantic_score += 35.0
            negative_score = max(0.0, negative_score - 20.0)

        boundary_y = separator_y if separator_y is not None else f_y0

        return {
            "page_number": page_number,
            "layout_score": min(60.0, layout_score),
            "multi_page_score": 0.0,  # Populated in multi-page step
            "semantic_score": min(45.0, semantic_score),
            "negative_score": negative_score,
            "boundary_y": boundary_y,
            "has_separator_line": has_separator,
            "separator_y": separator_y,
            "footer_bbox": footer_bbox,
            "negative_reasons": list(set(negative_reasons)),
            "candidate_texts": candidate_texts,
            "has_id_pair": has_id_pair,
            "has_explicit_labels": has_explicit_labels,
        }

    def _compute_multi_page_consistency(
        self,
        page_prelims: list[dict],
        total_pages: int,
    ) -> dict[int, float]:
        """Calculates multi-page repetition and layout consistency bonuses."""
        if total_pages < 2:
            return {}

        bonus_map: dict[int, float] = {}

        # Collect candidate Y coordinates from pages that have candidates and low negative score
        valid_pages = [
            p for p in page_prelims
            if p.get("status") != FooterStatus.DOCUMENT_UNREADABLE
            and p.get("footer_bbox") is not None
        ]

        if len(valid_pages) < 2:
            return {}

        for p in valid_pages:
            p_num = p["page_number"]
            p_y0 = p["footer_bbox"].y0
            # Allow variable vertical offsets (up to 80pt) across pages
            matching_peers = sum(
                1 for other in valid_pages
                if other["page_number"] != p_num and (
                    abs(other["footer_bbox"].y0 - p_y0) <= 80.0
                    or (p["candidate_texts"] and other["candidate_texts"] and any(
                        tc in pc or pc in tc for tc in other["candidate_texts"] for pc in p["candidate_texts"]
                    ))
                )
            )

            if matching_peers >= 2:
                bonus_map[p_num] = 25.0
            elif matching_peers >= 1:
                bonus_map[p_num] = 15.0
            elif matching_peers >= 1:
                bonus_map[p_num] = 15.0

        return bonus_map
