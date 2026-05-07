"""Line Reconstruction Engine.

Groups tokens into logical lines based on Y-coordinate proximity,
then sorts tokens within each line by X-coordinate for proper reading order.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.core.types import Token, ExtractedLine, PageData
from app.config import settings

logger = logging.getLogger(__name__)


class LineBuilder:
    """Reconstructs text lines from raw tokens using coordinate-based grouping."""

    def __init__(
        self,
        y_tolerance: Optional[float] = None,
        line_gap_threshold: Optional[float] = None,
    ):
        self.y_tolerance = y_tolerance or settings.TOKEN_Y_TOLERANCE
        self.line_gap_threshold = line_gap_threshold or settings.LINE_GAP_THRESHOLD

    def build_lines(self, page_data: PageData) -> list[ExtractedLine]:
        """Group tokens into lines for a single page.

        Algorithm:
        1. Sort tokens by y_center (top to bottom)
        2. Group tokens whose y_center is within y_tolerance
        3. Within each group, sort by x0 (left to right)
        4. Assign line numbers
        """
        if not page_data.tokens:
            return []

        sorted_tokens = sorted(page_data.tokens, key=lambda t: (t.y_center, t.x0))

        groups: list[list[Token]] = []
        current_group: list[Token] = [sorted_tokens[0]]

        for token in sorted_tokens[1:]:
            # Compare with the average y_center of the current group
            group_y_center = sum(t.y_center for t in current_group) / len(current_group)

            if abs(token.y_center - group_y_center) <= self.y_tolerance:
                current_group.append(token)
            else:
                groups.append(current_group)
                current_group = [token]

        if current_group:
            groups.append(current_group)

        lines: list[ExtractedLine] = []
        for line_num, group in enumerate(groups, start=1):
            # Sort tokens left to right within the line
            sorted_group = sorted(group, key=lambda t: t.x0)

            # Compute the average y_center for the line
            y_center = sum(t.y_center for t in sorted_group) / len(sorted_group)

            line = ExtractedLine(
                tokens=sorted_group,
                page=page_data.page_number,
                line_number=line_num,
                y_center=round(y_center, 2),
            )
            lines.append(line)

        logger.debug(
            f"Page {page_data.page_number}: {len(page_data.tokens)} tokens → {len(lines)} lines"
        )
        return lines

    def build_all_pages(self, pages: list[PageData]) -> list[PageData]:
        """Build lines for all pages, mutating PageData.lines in place."""
        for page in pages:
            page.lines = self.build_lines(page)
        return pages
