"""Tests for Document Image Preprocessing, Deskewing, and Patch Tiling (Module 7)."""

import numpy as np
from PIL import Image, ImageDraw
import pytest

from app.modules.document_digitizer.domain.preprocessor import DocumentPreprocessor


def test_preprocessor_grayscale_and_clean():
    preprocessor = DocumentPreprocessor()
    # Create clean image with text
    img = Image.new("RGB", (400, 300), color=(255, 255, 255))
    draw = ImageDraw.ImageDraw(img)
    draw.text((50, 50), "TEST DOCUMENT LINE 1", fill=(0, 0, 0))
    draw.text((50, 100), "TEST DOCUMENT LINE 2", fill=(0, 0, 0))

    deskewed, angle, meta = preprocessor.preprocess_image(img)
    assert deskewed.size == (400, 300)
    assert abs(angle) <= 1.0
    assert "original_dimensions" in meta


def test_preprocessor_skew_detection_and_correction():
    preprocessor = DocumentPreprocessor()
    # Create clean image with horizontal bands of text
    img = Image.new("RGB", (600, 600), color=(255, 255, 255))
    draw = ImageDraw.ImageDraw(img)
    for y in range(50, 500, 40):
        draw.rectangle([(50, y), (550, y + 15)], fill=(0, 0, 0))

    # Artificially rotate by 4.0 degrees
    rotated = img.rotate(4.0, expand=False, fillcolor=(255, 255, 255), resample=Image.BICUBIC)

    deskewed, detected_angle, meta = preprocessor.preprocess_image(rotated)
    # Detected angle should be close to 4.0 (within 1.5 degrees)
    assert abs(abs(detected_angle) - 4.0) < 1.5
    assert meta["deskew_applied"] is True


def test_preprocessor_patch_slicing_under_vram_limit():
    preprocessor = DocumentPreprocessor(max_patch_dimension=500, patch_overlap_px=50)
    # Image larger than 500x500 (e.g. 1100 x 900)
    large_img = Image.new("RGB", (1100, 900), color=(240, 240, 240))

    patches = preprocessor.slice_patches(large_img)
    assert len(patches) > 1
    for p in patches:
        assert p["width"] <= 500
        assert p["height"] <= 500
        assert p["image"].size[0] <= 500
        assert p["image"].size[1] <= 500

    # Test coordinate stitching
    local_box = (10, 20, 100, 150)
    stitched = preprocessor.stitch_bbox(local_box, offset_x=200, offset_y=300)
    assert stitched == (210, 320, 300, 450)

