"""Text Segmentation Service for DocMorph.

Extracts structured blocks, lines, spans, and coordinates from PyMuPDF pages,
preserving typography and providing sub-string bounding box resolution.
"""

from dataclasses import dataclass, field
from typing import Any, Optional
import pymupdf

from app.schemas.detection_data import BoundingBox, SpanInformation


@dataclass
class StructuredLine:
    """Represents a text line with full typography, coordinates, and hierarchy."""

    page_number: int
    block_number: int
    line_number: int
    text: str
    bbox: BoundingBox
    spans: list[SpanInformation] = field(default_factory=list)
    is_in_footer: bool = False


class TextSegmenter:
    """Extracts and organizes structured text lines and spans from PDF pages."""

    @classmethod
    def segment_page(
        cls,
        page: pymupdf.Page,
        page_number: int,
        footer_boundary_y: Optional[float] = None,
    ) -> list[StructuredLine]:
        """Extracts structured text lines with spans and bounding boxes from a page.

        Args:
            page: Open PyMuPDF Page object.
            page_number: 1-indexed page number.
            footer_boundary_y: Optional Y coordinate threshold for footer classification.

        Returns:
            List of StructuredLine objects in natural reading order.
        """
        page_dict: dict[str, Any] = page.get_text("dict")
        blocks = page_dict.get("blocks", [])

        lines: list[StructuredLine] = []

        for block_idx, block in enumerate(blocks):
            # Only process text blocks (type == 0)
            if block.get("type") != 0:
                continue

            block_lines = block.get("lines", [])
            for line_idx, raw_line in enumerate(block_lines):
                line_bbox_tuple = raw_line.get("bbox", (0, 0, 0, 0))
                line_bbox = BoundingBox.from_tuple(line_bbox_tuple)

                raw_spans = raw_line.get("spans", [])
                spans: list[SpanInformation] = []
                line_text_parts: list[str] = []

                for s in raw_spans:
                    span_text = s.get("text", "")
                    if span_text:
                        line_text_parts.append(span_text)
                    span_bbox_tuple = s.get("bbox", (0, 0, 0, 0))
                    spans.append(
                        SpanInformation(
                            text=span_text,
                            bbox=BoundingBox.from_tuple(span_bbox_tuple),
                            font=s.get("font", "unknown"),
                            size=round(float(s.get("size", 0.0)), 2),
                            color=int(s.get("color", 0)),
                            flags=int(s.get("flags", 0)),
                        )
                    )

                line_text = "".join(line_text_parts).strip()
                if not line_text:
                    continue

                # Determine if line is inside footer
                is_footer = False
                if footer_boundary_y is not None:
                    mid_y = (line_bbox.y0 + line_bbox.y1) / 2.0
                    is_footer = mid_y >= footer_boundary_y or line_bbox.y0 >= footer_boundary_y

                lines.append(
                    StructuredLine(
                        page_number=page_number,
                        block_number=block_idx,
                        line_number=line_idx,
                        text=line_text,
                        bbox=line_bbox,
                        spans=spans,
                        is_in_footer=is_footer,
                    )
                )

        return lines

    @classmethod
    def resolve_substring_bbox(
        cls,
        page: pymupdf.Page,
        substring: str,
        line: StructuredLine,
        start_char: int = 0,
        end_char: Optional[int] = None,
    ) -> BoundingBox:
        """Finds the precise bounding box of a substring within a text line.

        Attempts native PyMuPDF clipping search first, falling back to proportional
        coordinate interpolation if exact glyph search fails.

        Args:
            page: Open PyMuPDF Page object.
            substring: Substring to isolate.
            line: The StructuredLine containing the substring.
            start_char: Starting character index of substring in line.text.
            end_char: Ending character index of substring in line.text.

        Returns:
            Exact or interpolated BoundingBox.
        """
        clean_sub = substring.strip()
        if not clean_sub:
            return line.bbox

        # Try native clip search with PyMuPDF
        clip_rect = pymupdf.Rect(line.bbox.to_tuple())
        # Expand clip slightly vertically to ensure text is captured
        clip_rect.y0 -= 2.0
        clip_rect.y1 += 2.0

        try:
            matches = page.search_for(clean_sub, clip=clip_rect)
            if matches:
                # If multiple matches, pick the one closest to expected horizontal start
                if len(matches) == 1:
                    return BoundingBox.from_tuple(matches[0])
                else:
                    line_len = len(line.text) or 1
                    expected_x0 = line.bbox.x0 + (start_char / line_len) * line.bbox.width
                    best_rect = min(matches, key=lambda r: abs(r.x0 - expected_x0))
                    return BoundingBox.from_tuple(best_rect)
        except Exception:
            pass

        # Fallback: Proportional interpolation along line width
        line_len = len(line.text)
        if line_len <= 0 or end_char is None:
            return line.bbox

        fraction_start = max(0.0, min(1.0, start_char / line_len))
        fraction_end = max(fraction_start, min(1.0, end_char / line_len))

        interp_x0 = line.bbox.x0 + fraction_start * line.bbox.width
        interp_x1 = line.bbox.x0 + fraction_end * line.bbox.width

        return BoundingBox(
            x0=round(interp_x0, 2),
            y0=line.bbox.y0,
            x1=round(interp_x1, 2),
            y1=line.bbox.y1,
        )

