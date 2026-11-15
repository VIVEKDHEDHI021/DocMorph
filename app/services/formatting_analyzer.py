"""Formatting Analyzer Service for DocMorph.

Inspects original typography (font, size, flags, color, baseline origin),
maps fonts to standard PyMuPDF PDF font families, computes available horizontal space,
and calculates adaptive font scaling to prevent content collisions.
"""

from typing import Any, Optional
import pymupdf

from app.core.config import Settings, settings
from app.schemas.detection_data import BoundingBox, FieldOccurrence
from app.schemas.replacement_data import FormattingDetails


class FormattingAnalyzer:
    """Extracts typography details and computes safe geometric constraints for replacements."""

    def __init__(self, config: Settings = settings) -> None:
        """Initialize with application configuration limits.

        Args:
            config: Settings instance holding min font size and padding.
        """
        self.config = config
        self.min_font_size = config.MIN_REPLACEMENT_FONT_SIZE
        self.padding = config.DEFAULT_HORIZONTAL_PADDING

    @classmethod
    def map_font_name(cls, font_name: str, flags: int = 0) -> str:
        """Maps arbitrary PDF font names to PyMuPDF standard base font identifiers.

        Falls back gracefully to Helvetica if the font is embedded or unknown.

        Args:
            font_name: Original font name string.
            flags: PyMuPDF font flags (bit 1 = italic, bit 4 = bold).

        Returns:
            Standard PyMuPDF font code ('helv', 'hebo', 'heit', 'hebi', 'times', etc.).
        """
        is_bold = bool(flags & 16) or "bold" in font_name.lower() or "hebo" in font_name.lower()
        is_italic = (
            bool(flags & 2)
            or "italic" in font_name.lower()
            or "oblique" in font_name.lower()
            or "heit" in font_name.lower()
        )

        name_lower = font_name.lower()

        if "cour" in name_lower or "mono" in name_lower:
            if is_bold and is_italic:
                return "cobi"
            if is_bold:
                return "cobo"
            if is_italic:
                return "coit"
            return "cour"

        if "times" in name_lower or "serif" in name_lower or "roman" in name_lower:
            if is_bold and is_italic:
                return "tibi"
            if is_bold:
                return "tibo"
            if is_italic:
                return "tiit"
            return "tiro"

        # Default: Sans-serif (Helvetica)
        if is_bold and is_italic:
            return "hebi"
        if is_bold:
            return "hebo"
        if is_italic:
            return "heit"
        return "helv"

    @classmethod
    def convert_color_to_rgb(cls, color_int: int) -> tuple[float, float, float]:
        """Converts an integer 24-bit color (0xRRGGBB) to a normalized RGB float tuple.

        Args:
            color_int: Integer color representation.

        Returns:
            Tuple of (red, green, blue) floats in [0.0, 1.0].
        """
        if color_int <= 0:
            return (0.0, 0.0, 0.0)

        r = ((color_int >> 16) & 0xFF) / 255.0
        g = ((color_int >> 8) & 0xFF) / 255.0
        b = (color_int & 0xFF) / 255.0
        return (round(r, 3), round(g, 3), round(b, 3))

    def analyze_occurrence(
        self,
        page: pymupdf.Page,
        occurrence: FieldOccurrence,
        target_value: str,
    ) -> FormattingDetails:
        """Analyzes typography, baseline origin, and available width for a field occurrence.

        Args:
            page: Open PyMuPDF Page object.
            occurrence: The FieldOccurrence being replaced.
            target_value: The original value string to match.

        Returns:
            FormattingDetails instance with complete replacement specifications.
        """
        # Determine the target value bounding box
        val_bbox = occurrence.value_bbox or occurrence.bbox

        font_name = "Helvetica"
        font_size = 9.0
        font_flags = 0
        color_int = 0
        baseline_y = val_bbox.y1 - 2.0  # Sensible default baseline approximation

        # Scan text spans in dict to locate exact font and baseline origin
        page_dict: dict[str, Any] = page.get_text("dict")
        clip_rect = pymupdf.Rect(val_bbox.to_tuple())
        clip_rect.x0 -= 5.0
        clip_rect.x1 += 5.0
        clip_rect.y0 -= 4.0
        clip_rect.y1 += 4.0

        for block in page_dict.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    span_rect = pymupdf.Rect(span.get("bbox", (0, 0, 0, 0)))
                    # Check if span overlaps or contains the target value
                    if span_rect.intersects(clip_rect):
                        font_name = span.get("font", font_name)
                        font_size = float(span.get("size", font_size))
                        font_flags = int(span.get("flags", font_flags))
                        color_int = int(span.get("color", color_int))
                        origin = span.get("origin")
                        if origin and len(origin) == 2:
                            baseline_y = origin[1]
                        break

        mapped_font = self.map_font_name(font_name, font_flags)
        color_rgb = self.convert_color_to_rgb(color_int)

        # Calculate available width before the next element to the right
        available_width = self._compute_available_width(
            page=page,
            val_bbox=val_bbox,
            baseline_y=baseline_y,
        )

        origin_pt = (val_bbox.x0, baseline_y)

        return FormattingDetails(
            font_name=mapped_font,
            original_font=font_name,
            font_size=round(font_size, 2),
            font_flags=font_flags,
            color_rgb=color_rgb,
            origin=origin_pt,
            bbox=val_bbox,
            available_width=round(available_width, 2),
        )

    def _compute_available_width(
        self,
        page: pymupdf.Page,
        val_bbox: BoundingBox,
        baseline_y: float,
    ) -> float:
        """Determines the maximum horizontal clearance before striking adjacent content."""
        page_width = page.rect.width
        max_right_boundary = page_width - 20.0  # Standard page right margin
        nearest_x = max_right_boundary
        y_tolerance = 4.0

        # Scan all words on the page to find any obstacle on the same horizontal band to the right
        # Words format: (x0, y0, x1, y1, word_str, block_no, line_no, word_no)
        for w in page.get_text("words"):
            w_x0, w_y0, w_x1, w_y1, _, _, _, _ = w
            # Check if word is on the same vertical line band
            vertical_overlap = (
                abs(w_y1 - val_bbox.y1) <= y_tolerance
                or abs((w_y0 + w_y1) / 2.0 - (val_bbox.y0 + val_bbox.y1) / 2.0) <= y_tolerance
                or (w_y0 <= baseline_y <= w_y1)
            )
            if vertical_overlap:
                # Obstacle must start strictly to the right of the value's boundary
                if w_x0 > val_bbox.x0 + val_bbox.width * 0.9 and w_x0 >= val_bbox.x1 - 1.0:
                    if w_x0 < nearest_x:
                        nearest_x = w_x0

        # Also search text spans in dict for vector/custom positioned elements
        page_dict: dict[str, Any] = page.get_text("dict")
        for block in page_dict.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                line_bbox = pymupdf.Rect(line.get("bbox", (0, 0, 0, 0)))
                if (
                    abs(line_bbox.y1 - val_bbox.y1) <= y_tolerance
                    or abs((line_bbox.y0 + line_bbox.y1) / 2.0 - (val_bbox.y0 + val_bbox.y1) / 2.0)
                    <= y_tolerance
                    or (line_bbox.y0 <= baseline_y <= line_bbox.y1)
                ):
                    for span in line.get("spans", []):
                        span_bbox = pymupdf.Rect(span.get("bbox", (0, 0, 0, 0)))
                        if (
                            span_bbox.x0 > val_bbox.x0 + val_bbox.width * 0.9
                            and span_bbox.x0 >= val_bbox.x1 - 1.0
                        ):
                            if span_bbox.x0 < nearest_x:
                                nearest_x = span_bbox.x0

        clearance = nearest_x - val_bbox.x0 - self.padding
        # Ensure available width is never less than the original box width
        return max(val_bbox.width, clearance)

    @classmethod
    def normalize_base_font(cls, font_code: str) -> str:
        """Ensures the font identifier is a valid PyMuPDF Base-14 code recognized by get_text_length."""
        if not font_code:
            return "helv"
        fc = font_code.lower().strip()
        if fc in ("times", "times-roman", "timesroman", "ti", "tiro"):
            return "tiro"
        if fc in ("tibo", "times-bold"):
            return "tibo"
        if fc in ("tiit", "times-italic"):
            return "tiit"
        if fc in ("tibi", "times-bolditalic"):
            return "tibi"
        if fc in ("cour", "courier", "mono"):
            return "cour"
        if fc in ("cobo", "coit", "cobi"):
            return fc
        if fc in ("helv", "hebo", "heit", "hebi"):
            return fc
        return cls.map_font_name(font_code)

    def calculate_fitted_font_size(
        self,
        text: str,
        font_name: str,
        base_font_size: float,
        available_width: float,
    ) -> tuple[float, bool, Optional[str]]:
        """Calculates adaptive font size scaling to fit within available width.

        Args:
            text: Replacement text string.
            font_name: PyMuPDF font identifier.
            base_font_size: Original font size in points.
            available_width: Available width in points.

        Returns:
            Tuple of (final_font_size, has_collision, warning_message).
        """
        font_name = self.normalize_base_font(font_name)
        try:
            text_width = pymupdf.get_text_length(text, fontname=font_name, fontsize=base_font_size)
        except Exception:
            font_name = "tiro" if "ti" in font_name else "helv"
            try:
                text_width = pymupdf.get_text_length(text, fontname=font_name, fontsize=base_font_size)
            except Exception:
                font_name = "helv"
                text_width = pymupdf.get_text_length(text, fontname="helv", fontsize=base_font_size)

        if text_width <= available_width:
            return (base_font_size, False, None)

        # Scale down gradually
        scale_factor = available_width / text_width
        scaled_size = round(base_font_size * scale_factor, 2)

        if scaled_size >= self.min_font_size:
            warning = (
                f"Replacement text was scaled from {base_font_size:.1f}pt to {scaled_size:.1f}pt "
                f"to fit available width ({available_width:.1f}pt)."
            )
            return (scaled_size, False, warning)

        # Below minimum allowed font size: collision detected
        collision_msg = (
            f"Replacement text '{text}' requires {text_width:.1f}pt at base size {base_font_size}pt, "
            f"exceeding available width of {available_width:.1f}pt (scales below min {self.min_font_size}pt)."
        )
        return (self.min_font_size, True, collision_msg)
