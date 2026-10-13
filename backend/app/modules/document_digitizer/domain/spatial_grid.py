"""Spatial 2D Grid Reconstruction and Tabular Layout Alignment (Module 7).

Organizes unordered token bounding boxes into natural reading order and tabular rows/columns
without hardcoding fixed pixel offsets, preventing model overfitting and brittleness.
"""

from typing import List, Dict, Any, Optional, Tuple
from app.modules.document_digitizer.domain.models import BoundingBox, ExtractedToken, DocumentLineItem


class SpatialGridReconstructor:
    """Reconstructs reading order and multi-column tabular structure from 2D coordinates."""

    def __init__(self, vertical_overlap_threshold: float = 0.45, row_merge_tolerance_px: int = 12):
        self.vertical_overlap_threshold = vertical_overlap_threshold
        self.row_merge_tolerance_px = row_merge_tolerance_px

    def sort_reading_order(self, tokens: List[ExtractedToken]) -> List[ExtractedToken]:
        """Sort tokens into top-to-bottom, left-to-right reading order."""
        if not tokens:
            return []

        # Group tokens into horizontal rows
        rows = self.cluster_tokens_into_rows(tokens)

        # Within each row, sort left-to-right by x1
        ordered_tokens: List[ExtractedToken] = []
        global_idx = 0
        for r in rows:
            r_sorted = sorted(r, key=lambda t: t.bbox.x1)
            for tok in r_sorted:
                tok.reading_order_index = global_idx
                ordered_tokens.append(tok)
                global_idx += 1

        return ordered_tokens

    def cluster_tokens_into_rows(self, tokens: List[ExtractedToken]) -> List[List[ExtractedToken]]:
        """
        Cluster tokens into visual horizontal rows based on vertical overlap.
        Tokens that share significant vertical intersection belong to the same text line.
        """
        if not tokens:
            return []

        # Sort initially by top edge y1
        sorted_by_y = sorted(tokens, key=lambda t: t.bbox.y1)
        rows: List[List[ExtractedToken]] = []

        for tok in sorted_by_y:
            placed = False
            for row in rows:
                # Compare vertical overlap with the row's representative median vertical span
                row_y1 = min(t.bbox.y1 for t in row)
                row_y2 = max(t.bbox.y2 for t in row)
                row_h = max(1, row_y2 - row_y1)

                tok_y1 = tok.bbox.y1
                tok_y2 = tok.bbox.y2
                tok_h = max(1, tok_y2 - tok_y1)

                overlap_y = max(0, min(row_y2, tok_y2) - max(row_y1, tok_y1))
                min_h = min(row_h, tok_h)

                if (overlap_y / min_h) >= self.vertical_overlap_threshold or abs(tok.bbox.center_y - ((row_y1 + row_y2) / 2.0)) < 0.015:
                    row.append(tok)
                    placed = True
                    break

            if not placed:
                rows.append([tok])

        # Sort the rows top-to-bottom based on average y1
        rows.sort(key=lambda r: sum(t.bbox.y1 for t in r) / len(r))
        return rows

    def extract_tabular_lines(self, rows: List[List[ExtractedToken]]) -> List[Dict[str, Any]]:
        """
        Converts clustered text rows into structured line entries with text,
        numeric amount candidates, and combined bounding boxes.
        """
        table_lines = []
        for row in rows:
            # Sort tokens in row left-to-right
            row_sorted = sorted(row, key=lambda t: t.bbox.x1)
            full_text = " ".join(t.text for t in row_sorted).strip()
            if not full_text:
                continue

            rx1 = min(t.bbox.x1 for t in row_sorted)
            ry1 = min(t.bbox.y1 for t in row_sorted)
            rx2 = max(t.bbox.x2 for t in row_sorted)
            ry2 = max(t.bbox.y2 for t in row_sorted)

            # Detect numeric tokens on the right side of the row
            num_tokens = []
            for t in row_sorted:
                cleaned = t.text.replace(",", "").replace("$", "").replace("PKR", "").strip()
                if cleaned in ("-", "—", "--"):
                    num_tokens.append({
                        "token": t,
                        "value": 0.0,
                        "raw_text": t.text,
                    })
                    continue

                # Handle parenthetical accounting negatives e.g. (1,200.00) or -1200
                is_neg = False
                if cleaned.startswith("(") and cleaned.endswith(")"):
                    cleaned = cleaned[1:-1]
                    is_neg = True
                elif cleaned.startswith("-") and len(cleaned) > 1:
                    cleaned = cleaned[1:]
                    is_neg = True

                try:
                    val = float(cleaned)
                    num_tokens.append({
                        "token": t,
                        "value": -val if is_neg else val,
                        "raw_text": t.text,
                    })
                except ValueError:
                    pass

            table_lines.append({
                "tokens": row_sorted,
                "text": full_text,
                "bbox_pixels": [rx1, ry1, rx2, ry2],
                "numeric_tokens": num_tokens,
            })

        return table_lines
