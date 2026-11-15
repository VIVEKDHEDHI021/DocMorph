"""Footer Region Detection Service for DocMorph.

Identifies potential footer candidate regions using page geometry, orientation,
configurable height ratios, and adaptive layout gap detection.
"""

from typing import Optional
import pymupdf
from app.core.config import Settings, settings
from app.schemas.detection_data import BoundingBox


class FooterDetector:
    """Service for identifying geometric footer zones across varying page layouts."""

    def __init__(self, config: Settings = settings) -> None:
        """Initialize with application configuration settings.

        Args:
            config: Settings instance holding default footer boundaries.
        """
        self.config = config
        self.default_ratio = config.FOOTER_HEIGHT_PERCENT

    def get_footer_boundary_y(
        self,
        page_height: float,
        ratio: Optional[float] = None,
    ) -> float:
        """Returns the Y-coordinate boundary above which text is considered body/header.

        Text with y >= footer_boundary_y falls within the bottom footer region.

        Args:
            page_height: Total page height in points.
            ratio: Optional override for the bottom height fraction (e.g. 0.20 for bottom 20%).

        Returns:
            The Y coordinate marking the start of the footer region.
        """
        effective_ratio = ratio if ratio is not None else self.default_ratio
        clamped_ratio = max(0.05, min(0.50, effective_ratio))
        return page_height * (1.0 - clamped_ratio)

    def get_footer_region(
        self,
        page_width: float,
        page_height: float,
        ratio: Optional[float] = None,
    ) -> BoundingBox:
        """Returns the bounding box encompassing the geometric footer zone.

        Supports both portrait and landscape page orientations.

        Args:
            page_width: Total page width in points.
            page_height: Total page height in points.
            ratio: Optional bottom fraction override.

        Returns:
            BoundingBox representing the full footer area.
        """
        y_start = self.get_footer_boundary_y(page_height, ratio)
        return BoundingBox(
            x0=0.0,
            y0=round(y_start, 2),
            x1=round(page_width, 2),
            y1=round(page_height, 2),
        )

    def is_in_footer(
        self,
        bbox: BoundingBox,
        page_height: float,
        ratio: Optional[float] = None,
    ) -> bool:
        """Evaluates whether a given text bounding box resides within the footer zone.

        Evaluates the vertical center of the bounding box to prevent false negatives
        when a text line spans slightly above the exact threshold.

        Args:
            bbox: BoundingBox to inspect.
            page_height: Height of the document page.
            ratio: Optional fraction override.

        Returns:
            True if the element is located in the footer region.
        """
        boundary_y = self.get_footer_boundary_y(page_height, ratio)
        mid_y = (bbox.y0 + bbox.y1) / 2.0
        return mid_y >= boundary_y or bbox.y0 >= boundary_y

    def detect_adaptive_footer_boundary(
        self,
        line_bboxes: list[BoundingBox],
        page_height: float,
        max_scan_ratio: float = 0.30,
    ) -> float:
        """Detects an adaptive footer boundary by analyzing whitespace gaps near page bottom.

        If an isolated footer line is situated slightly higher than the default 20%
        boundary (up to max_scan_ratio, e.g. 30%), separated by a significant vertical gap
        from the body text, this method adapts the boundary to encompass it.

        Args:
            line_bboxes: List of line bounding boxes on the page.
            page_height: Total page height.
            max_scan_ratio: Maximum height fraction from bottom to consider for a footer.

        Returns:
            The adaptive Y coordinate boundary.
        """
        if not line_bboxes:
            return self.get_footer_boundary_y(page_height)

        # Sort lines vertically from top to bottom
        sorted_boxes = sorted(line_bboxes, key=lambda b: b.y0)
        scan_boundary_y = page_height * (1.0 - max_scan_ratio)

        # Find lines that fall in the lower portion of the page
        candidate_indices = [
            i for i, b in enumerate(sorted_boxes) if b.y0 >= scan_boundary_y
        ]

        if not candidate_indices:
            return self.get_footer_boundary_y(page_height)

        # Look for the largest vertical gap preceding the bottom candidates
        best_boundary_y = self.get_footer_boundary_y(page_height)
        max_gap = 0.0

        first_cand_idx = candidate_indices[0]
        if first_cand_idx > 0:
            prev_line = sorted_boxes[first_cand_idx - 1]
            first_cand = sorted_boxes[first_cand_idx]
            gap = first_cand.y0 - prev_line.y1
            # If gap between body text and footer line is at least 15 points
            if gap >= 15.0 and gap > max_gap:
                best_boundary_y = first_cand.y0 - 5.0

        return best_boundary_y

    @classmethod
    def find_footer_separator_line(cls, page: pymupdf.Page) -> Optional[float]:
        """Detects a horizontal separator line/rule in the lower region of the page.

        Inspects vector drawings for thin horizontal strokes or rectangles spanning
        at least 35% of the page width in the lower 40% of the page.

        Args:
            page: Open PyMuPDF Page instance.

        Returns:
            Y-coordinate of the separator line, or None if not present.
        """
        page_height = page.rect.height
        page_width = page.rect.width
        min_y = page_height * 0.60

        try:
            drawings = page.get_drawings()
            for d in drawings:
                rect = d.get("rect")
                if not rect:
                    continue
                # Line must be in the lower 40% of page
                if rect.y0 < min_y:
                    continue
                # Wide horizontal rule
                if rect.width >= page_width * 0.35 and rect.height <= 4.0:
                    return round((rect.y0 + rect.y1) / 2.0, 2)

                # Check items for line commands ("l", p1, p2)
                for item in d.get("items", []):
                    if item[0] == "l":
                        p1, p2 = item[1], item[2]
                        if abs(p1.y - p2.y) <= 2.0 and p1.y >= min_y:
                            line_w = abs(p2.x - p1.x)
                            if line_w >= page_width * 0.35:
                                return round((p1.y + p2.y) / 2.0, 2)
        except Exception:
            pass

        return None

    @classmethod
    def is_near_separator_line(
        cls,
        bbox: BoundingBox,
        separator_y: Optional[float],
        tolerance: float = 40.0,
    ) -> bool:
        """Determines if a bounding box is positioned immediately near a separator line."""
        if separator_y is None:
            return False
        return (
            abs(bbox.y0 - separator_y) <= tolerance
            or abs(bbox.y1 - separator_y) <= tolerance
            or (bbox.y0 >= separator_y - 10.0 and bbox.y0 <= separator_y + tolerance)
        )

    @classmethod
    def is_bottom_left(
        cls,
        bbox: BoundingBox,
        page_width: float,
        page_height: float,
    ) -> bool:
        """Determines if a bounding box is located in the bottom-left region of the page."""
        is_lower = bbox.y0 >= page_height * 0.60
        is_left = bbox.x0 <= page_width * 0.48
        return is_lower and is_left


