"""Tests for Spatial Grid Reconstruction and Reading Order Alignment (Module 7)."""

import pytest
from app.modules.document_digitizer.domain.models import BoundingBox, ExtractedToken
from app.modules.document_digitizer.domain.spatial_grid import SpatialGridReconstructor


def test_spatial_grid_reading_order_sorting():
    grid = SpatialGridReconstructor()

    # Create shuffled tokens on 3 lines
    # Line 1: y in [50, 70]
    t1 = ExtractedToken(token_id="1", text="Company", bbox=BoundingBox.from_pixels(50, 50, 150, 70, 800, 1000))
    t2 = ExtractedToken(token_id="2", text="Name", bbox=BoundingBox.from_pixels(160, 50, 220, 70, 800, 1000))
    # Line 2: y in [100, 120]
    t3 = ExtractedToken(token_id="3", text="Invoice", bbox=BoundingBox.from_pixels(50, 100, 120, 120, 800, 1000))
    t4 = ExtractedToken(token_id="4", text="#1001", bbox=BoundingBox.from_pixels(130, 100, 200, 120, 800, 1000))
    # Line 3: y in [150, 170]
    t5 = ExtractedToken(token_id="5", text="Total:", bbox=BoundingBox.from_pixels(50, 150, 100, 170, 800, 1000))
    t6 = ExtractedToken(token_id="6", text="5,000.00", bbox=BoundingBox.from_pixels(300, 150, 380, 170, 800, 1000))

    shuffled = [t4, t6, t1, t5, t2, t3]
    ordered = grid.sort_reading_order(shuffled)

    texts = [t.text for t in ordered]
    assert texts == ["Company", "Name", "Invoice", "#1001", "Total:", "5,000.00"]


def test_spatial_grid_parenthetical_negative_handling():
    grid = SpatialGridReconstructor()

    t_lbl = ExtractedToken(token_id="1", text="Less Discount", bbox=BoundingBox.from_pixels(50, 100, 180, 120, 800, 1000))
    t_val = ExtractedToken(token_id="2", text="(1,250.00)", bbox=BoundingBox.from_pixels(400, 100, 480, 120, 800, 1000))

    rows = grid.cluster_tokens_into_rows([t_lbl, t_val])
    lines = grid.extract_tabular_lines(rows)

    assert len(lines) == 1
    nums = lines[0]["numeric_tokens"]
    assert len(nums) == 1
    # Parenthetical accounting number (1,250.00) must parse to negative float -1250.0
    assert nums[0]["value"] == -1250.0

