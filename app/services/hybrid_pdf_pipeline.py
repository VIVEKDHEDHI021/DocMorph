"""Hybrid PDF Input Pipeline for DocMorph.

Provides unified, robust document ingestion supporting:
1. Native-text PDFs: Precise vector typography, character spans, and bounding boxes via PyMuPDF.
2. Scanned PDFs: Automated rasterization, OCR text extraction, word bounding boxes, and confidence.
3. Mixed PDFs: Selective OCR application only on non-selectable regions without word duplication.
4. Unified Intermediate Representation: Normalized [0, 1000] LayoutLM-compatible spatial coordinates.
"""

from dataclasses import dataclass, field
import io
import math
from pathlib import Path
from typing import Any, Literal, Optional
from PIL import Image
import pymupdf

from app.core.exceptions import PDFValidationError
from app.utils.file_validator import FileValidator


@dataclass
class ExtractedToken:
    """Represents an individual word token with spatial, typographical, and provenance metadata."""

    text: str
    bbox: tuple[float, float, float, float]  # (x0, y0, x1, y1) in original PDF points
    normalized_bbox: tuple[int, int, int, int]  # (x0, y0, x1, y1) mapped to [0, 1000] integer scale
    page_number: int
    font: str = "unknown"
    size: float = 10.0
    flags: int = 0
    color: int = 0
    source: Literal["native", "ocr"] = "native"
    confidence: float = 1.0  # 1.0 for native digital text, 0.0-1.0 for OCR output


@dataclass
class HybridTextLine:
    """Represents a coherent line composed of ordered tokens."""

    line_number: int
    page_number: int
    text: str
    bbox: tuple[float, float, float, float]
    normalized_bbox: tuple[int, int, int, int]
    tokens: list[ExtractedToken] = field(default_factory=list)
    source: Literal["native", "ocr", "mixed"] = "native"
    is_in_footer_zone: bool = False


@dataclass
class PageRepresentation:
    """Complete multi-modal representation of a document page."""

    page_number: int
    width: float
    height: float
    is_scanned: bool
    is_mixed: bool
    tokens: list[ExtractedToken] = field(default_factory=list)
    lines: list[HybridTextLine] = field(default_factory=list)
    image_bytes: Optional[bytes] = None
    horizontal_separator_y: Optional[float] = None


@dataclass
class DocumentRepresentation:
    """Complete structured intermediate representation of a document."""

    document_id: str
    filename: str
    total_pages: int
    pages: list[PageRepresentation] = field(default_factory=list)


class HybridPDFPipeline:
    """Orchestrates native digital extraction, adaptive OCR fallback, and normalization."""

    def __init__(self, dpi: int = 150):
        self.dpi = dpi

    @staticmethod
    def normalize_box(
        box: tuple[float, float, float, float],
        page_width: float,
        page_height: float,
    ) -> tuple[int, int, int, int]:
        """Maps PDF point coordinates to standard LayoutLM [0, 1000] integer coordinates."""
        if page_width <= 0 or page_height <= 0:
            return (0, 0, 0, 0)

        x0, y0, x1, y1 = box
        nx0 = max(0, min(1000, int(round((x0 / page_width) * 1000))))
        ny0 = max(0, min(1000, int(round((y0 / page_height) * 1000))))
        nx1 = max(0, min(1000, int(round((x1 / page_width) * 1000))))
        ny1 = max(0, min(1000, int(round((y1 / page_height) * 1000))))

        # Ensure valid dimensions
        if nx1 < nx0:
            nx0, nx1 = nx1, nx0
        if ny1 < ny0:
            ny0, ny1 = ny1, ny0
        if nx1 == nx0:
            nx1 = min(1000, nx0 + 1)
        if ny1 == ny0:
            ny1 = min(1000, ny0 + 1)

        return (nx0, ny0, nx1, ny1)

    def process_document(
        self,
        doc: pymupdf.Document,
        document_id: str = "doc_unknown",
        filename: str = "document.pdf",
    ) -> DocumentRepresentation:
        """Processes an open PyMuPDF document into the intermediate representation."""
        page_reps: list[PageRepresentation] = []

        for page_idx, page in enumerate(doc, start=1):
            page_rep = self.process_page(page, page_number=page_idx)
            page_reps.append(page_rep)

        return DocumentRepresentation(
            document_id=document_id,
            filename=filename,
            total_pages=len(page_reps),
            pages=page_reps,
        )

    def process_file(
        self,
        file_path: Path | str,
        document_id: str = "doc_unknown",
    ) -> DocumentRepresentation:
        """Loads and processes a PDF file from disk."""
        resolved = Path(file_path).resolve()
        with pymupdf.open(str(resolved)) as doc:
            FileValidator.validate_pdf_document(doc)
            return self.process_document(doc, document_id=document_id, filename=resolved.name)

    def process_bytes(
        self,
        pdf_bytes: bytes,
        document_id: str = "doc_unknown",
        filename: str = "document.pdf",
    ) -> DocumentRepresentation:
        """Loads and processes PDF bytes from memory."""
        with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
            FileValidator.validate_pdf_document(doc)
            return self.process_document(doc, document_id=document_id, filename=filename)

    def process_page(
        self,
        page: pymupdf.Page,
        page_number: int,
    ) -> PageRepresentation:
        """Extracts native text, applies OCR fallback if scanned or mixed, and groups into lines."""
        p_width = float(page.rect.width)
        p_height = float(page.rect.height)

        # 1. Inspect native digital text
        native_words = page.get_text("words")  # (x0, y0, x1, y1, word, block_no, line_no, word_no)
        native_dict = page.get_text("dict")

        is_scanned = len(native_words) < 5
        is_mixed = False
        all_tokens: list[ExtractedToken] = []

        if not is_scanned:
            # High-fidelity native extraction
            all_tokens = self._extract_native_tokens(native_words, native_dict, p_width, p_height, page_number)

            # Check if lower margin (footer zone) is an image that might have non-native text
            footer_rect = pymupdf.Rect(0, p_height * 0.70, p_width, p_height)
            footer_native_count = sum(1 for t in all_tokens if t.bbox[1] >= p_height * 0.70)
            images_in_footer = self._has_images_in_rect(page, footer_rect)

            if footer_native_count == 0 and images_in_footer:
                # Potential mixed document: apply targeted OCR on footer region
                ocr_tokens = self._apply_targeted_ocr(page, footer_rect, p_width, p_height, page_number)
                if ocr_tokens:
                    is_mixed = True
                    all_tokens.extend(ocr_tokens)
        else:
            # Scanned document: execute full-page OCR
            ocr_tokens = self._apply_full_page_ocr(page, p_width, p_height, page_number)
            all_tokens = ocr_tokens

        # Sort tokens in natural top-to-bottom, left-to-right reading order
        all_tokens.sort(key=lambda t: (round(t.bbox[1] / 6.0), t.bbox[0]))

        # Group tokens into lines
        lines = self._group_tokens_into_lines(all_tokens, p_width, p_height, page_number)

        # Check for horizontal separator lines
        sep_y = self._find_horizontal_separator(page)

        # Tag footer region lines
        for line in lines:
            mid_y = (line.bbox[1] + line.bbox[3]) / 2.0
            if sep_y is not None and mid_y >= sep_y:
                line.is_in_footer_zone = True
            elif mid_y >= p_height * 0.80:
                line.is_in_footer_zone = True

        return PageRepresentation(
            page_number=page_number,
            width=p_width,
            height=p_height,
            is_scanned=is_scanned,
            is_mixed=is_mixed,
            tokens=all_tokens,
            lines=lines,
            image_bytes=None,  # Render on-demand to save memory
            horizontal_separator_y=sep_y,
        )

    def _extract_native_tokens(
        self,
        words: list[Any],
        page_dict: dict[str, Any],
        page_width: float,
        page_height: float,
        page_number: int,
    ) -> list[ExtractedToken]:
        """Extracts native word tokens matched with typography metadata from the page dict."""
        tokens: list[ExtractedToken] = []

        # Build spatial span index for fast typography lookup
        spans_index: list[dict[str, Any]] = []
        for block in page_dict.get("blocks", []):
            if block.get("type") == 0:
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        s_box = span.get("bbox", (0, 0, 0, 0))
                        spans_index.append({
                            "rect": pymupdf.Rect(s_box),
                            "font": span.get("font", "unknown"),
                            "size": float(span.get("size", 10.0)),
                            "flags": int(span.get("flags", 0)),
                            "color": int(span.get("color", 0)),
                        })

        for w in words:
            text = str(w[4]).strip()
            if not text:
                continue

            x0, y0, x1, y1 = float(w[0]), float(w[1]), float(w[2]), float(w[3])
            bbox = (round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2))
            norm_box = self.normalize_box(bbox, page_width, page_height)

            # Match span metadata
            w_rect = pymupdf.Rect(x0, y0, x1, y1)
            font, size, flags, color = "unknown", 10.0, 0, 0
            for sp in spans_index:
                if sp["rect"].intersects(w_rect):
                    font = sp["font"]
                    size = sp["size"]
                    flags = sp["flags"]
                    color = sp["color"]
                    break

            tokens.append(
                ExtractedToken(
                    text=text,
                    bbox=bbox,
                    normalized_bbox=norm_box,
                    page_number=page_number,
                    font=font,
                    size=size,
                    flags=flags,
                    color=color,
                    source="native",
                    confidence=1.0,
                )
            )

        return tokens

    def _apply_full_page_ocr(
        self,
        page: pymupdf.Page,
        page_width: float,
        page_height: float,
        page_number: int,
    ) -> list[ExtractedToken]:
        """Applies OCR across a scanned page using PyMuPDF TextPage OCR or image fallback."""
        tokens: list[ExtractedToken] = []

        try:
            # PyMuPDF 2.0 TextPage OCR
            textpage = page.get_textpage_ocr(flags=0, dpi=self.dpi, full=True)
            words = textpage.extractWORDS()
            for w in words:
                text = str(w[4]).strip()
                if not text:
                    continue
                bbox = (round(w[0], 2), round(w[1], 2), round(w[2], 2), round(w[3], 2))
                norm_box = self.normalize_box(bbox, page_width, page_height)
                tokens.append(
                    ExtractedToken(
                        text=text,
                        bbox=bbox,
                        normalized_bbox=norm_box,
                        page_number=page_number,
                        font="OCR",
                        size=9.0,
                        flags=0,
                        color=0,
                        source="ocr",
                        confidence=0.88,
                    )
                )
        except Exception:
            # Fallback: extract native words if any exist
            native_words = page.get_text("words")
            for w in native_words:
                text = str(w[4]).strip()
                if not text:
                    continue
                bbox = (round(w[0], 2), round(w[1], 2), round(w[2], 2), round(w[3], 2))
                norm_box = self.normalize_box(bbox, page_width, page_height)
                tokens.append(
                    ExtractedToken(
                        text=text,
                        bbox=bbox,
                        normalized_bbox=norm_box,
                        page_number=page_number,
                        source="ocr",
                        confidence=0.75,
                    )
                )

        return tokens

    def _apply_targeted_ocr(
        self,
        page: pymupdf.Page,
        clip_rect: pymupdf.Rect,
        page_width: float,
        page_height: float,
        page_number: int,
    ) -> list[ExtractedToken]:
        """Applies targeted OCR to a specific sub-region on a mixed-content page."""
        tokens: list[ExtractedToken] = []
        try:
            textpage = page.get_textpage_ocr(clip=clip_rect, dpi=self.dpi)
            words = textpage.extractWORDS()
            for w in words:
                text = str(w[4]).strip()
                if not text:
                    continue
                bbox = (round(w[0], 2), round(w[1], 2), round(w[2], 2), round(w[3], 2))
                norm_box = self.normalize_box(bbox, page_width, page_height)
                tokens.append(
                    ExtractedToken(
                        text=text,
                        bbox=bbox,
                        normalized_bbox=norm_box,
                        page_number=page_number,
                        font="OCR",
                        source="ocr",
                        confidence=0.85,
                    )
                )
        except Exception:
            pass
        return tokens

    @staticmethod
    def _has_images_in_rect(page: pymupdf.Page, rect: pymupdf.Rect) -> bool:
        """Checks if any embedded images intersect the given rectangle."""
        try:
            image_list = page.get_images()
            if not image_list:
                return False
            for img_info in page.get_image_info():
                img_bbox = pymupdf.Rect(img_info.get("bbox", (0, 0, 0, 0)))
                if img_bbox.intersects(rect):
                    return True
        except Exception:
            pass
        return False

    def _find_horizontal_separator(self, page: pymupdf.Page) -> Optional[float]:
        """Locates horizontal graphical lines in the bottom half of the page."""
        try:
            drawings = page.get_drawings()
            candidates: list[float] = []
            page_w = page.rect.width
            page_h = page.rect.height

            for draw in drawings:
                rect = draw.get("rect")
                if not rect:
                    continue
                r = pymupdf.Rect(rect)
                # Must be in bottom 40% of page
                if r.y0 < page_h * 0.60:
                    continue
                # Line characteristics: thin height, wide horizontal span
                if r.height <= 4.0 and r.width >= page_w * 0.50:
                    candidates.append(r.y0)

            if candidates:
                # Return the highest line in the lower zone that acts as separator
                return min(candidates)
        except Exception:
            pass
        return None

    def _group_tokens_into_lines(
        self,
        tokens: list[ExtractedToken],
        page_width: float,
        page_height: float,
        page_number: int,
    ) -> list[HybridTextLine]:
        """Clusters extracted tokens into logical text lines based on horizontal baseline alignment."""
        if not tokens:
            return []

        lines: list[HybridTextLine] = []
        current_tokens: list[ExtractedToken] = [tokens[0]]

        for tok in tokens[1:]:
            prev_tok = current_tokens[-1]
            # Same line if vertical overlap or close Y centers
            prev_mid_y = (prev_tok.bbox[1] + prev_tok.bbox[3]) / 2.0
            curr_mid_y = (tok.bbox[1] + tok.bbox[3]) / 2.0

            if abs(curr_mid_y - prev_mid_y) <= 3.5:
                current_tokens.append(tok)
            else:
                # Finish line
                current_tokens.sort(key=lambda t: t.bbox[0])
                line = self._create_line_from_tokens(current_tokens, page_width, page_height, len(lines) + 1, page_number)
                lines.append(line)
                current_tokens = [tok]

        if current_tokens:
            current_tokens.sort(key=lambda t: t.bbox[0])
            line = self._create_line_from_tokens(current_tokens, page_width, page_height, len(lines) + 1, page_number)
            lines.append(line)

        return lines

    def _create_line_from_tokens(
        self,
        tokens: list[ExtractedToken],
        page_width: float,
        page_height: float,
        line_num: int,
        page_number: int,
    ) -> HybridTextLine:
        """Constructs a HybridTextLine instance from ordered tokens."""
        line_text = " ".join(t.text for t in tokens)
        x0 = min(t.bbox[0] for t in tokens)
        y0 = min(t.bbox[1] for t in tokens)
        x1 = max(t.bbox[2] for t in tokens)
        y1 = max(t.bbox[3] for t in tokens)
        bbox = (round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2))
        norm_bbox = self.normalize_box(bbox, page_width, page_height)

        sources = {t.source for t in tokens}
        src: Literal["native", "ocr", "mixed"] = (
            "mixed" if len(sources) > 1 else list(sources)[0]
        )

        return HybridTextLine(
            line_number=line_num,
            page_number=page_number,
            text=line_text,
            bbox=bbox,
            normalized_bbox=norm_bbox,
            tokens=tokens,
            source=src,
        )

    def render_page_image(self, page: pymupdf.Page) -> Image.Image:
        """Renders a PDF page to a PIL Image at pipeline DPI."""
        pix = page.get_pixmap(dpi=self.dpi)
        img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
        return img

