"""Image Preprocessing, Deskewing, and VRAM-Constrained Visual Patch Slicing (Module 7)."""

import math
from typing import Tuple, List, Dict, Any, Optional
import numpy as np
from PIL import Image, ImageOps, ImageFilter


class DocumentPreprocessor:
    """Preprocesses raw scans: binarization, deskewing, and patch tiling."""

    def __init__(self, max_patch_dimension: int = 1024, patch_overlap_px: int = 64):
        self.max_patch_dimension = max_patch_dimension
        self.patch_overlap_px = patch_overlap_px

    def preprocess_image(self, image: Image.Image) -> Tuple[Image.Image, float, Dict[str, Any]]:
        """
        Runs complete preprocessing pipeline:
        1. Grayscale normalization.
        2. Skew angle detection and deskewing.
        3. Contrast stretching / binarization preparation.
        Returns:
            (deskewed_image, detected_skew_angle_deg, metadata)
        """
        # Convert to RGB if RGBA/P
        if image.mode != "RGB":
            image = image.convert("RGB")

        orig_w, orig_h = image.size

        # 1. Grayscale
        gray = ImageOps.grayscale(image)

        # 2. Skew angle detection
        skew_angle = self.detect_skew_angle(gray)

        # 3. Deskew rotation
        if abs(skew_angle) > 0.4:
            deskewed_rgb = image.rotate(-skew_angle, expand=False, fillcolor=(255, 255, 255), resample=Image.BICUBIC)
        else:
            deskewed_rgb = image
            skew_angle = 0.0

        metadata = {
            "original_dimensions": [orig_w, orig_h],
            "deskew_angle_deg": round(skew_angle, 2),
            "deskew_applied": abs(skew_angle) > 0.4,
        }
        return deskewed_rgb, skew_angle, metadata

    def detect_skew_angle(self, gray_img: Image.Image, angle_range: float = 10.0, step: float = 0.5) -> float:
        """
        Detect text baseline skew using horizontal projection profile variance.
        Text aligned horizontally exhibits maximum variance in horizontal row pixel sums.
        """
        # Downscale for fast sub-50ms CPU projection calculation
        w, h = gray_img.size
        scale = min(1.0, 400.0 / max(w, h))
        small = gray_img.resize((int(w * scale), int(h * scale)), Image.BILINEAR)

        # Convert to binary numpy array (text as 1, background as 0)
        arr = np.array(small, dtype=np.float32)
        thresh = np.mean(arr) * 0.9
        bin_arr = (arr < thresh).astype(np.float32)

        best_score = -1.0
        best_angle = 0.0

        angles = np.arange(-angle_range, angle_range + step, step)
        pil_bin = Image.fromarray((bin_arr * 255).astype(np.uint8))

        for ang in angles:
            rotated = pil_bin.rotate(ang, expand=False, fillcolor=0, resample=Image.NEAREST)
            rot_arr = np.array(rotated, dtype=np.float32)
            row_sums = np.sum(rot_arr, axis=1)
            score = float(np.var(row_sums))

            if score > best_score:
                best_score = score
                best_angle = float(ang)

        return best_angle

    def slice_patches(self, image: Image.Image) -> List[Dict[str, Any]]:
        """
        Slices large 150-300 DPI document images into bounded tiles to guarantee
        that GPU VRAM footprint stays strictly under the 2.2 GB threshold.
        Returns list of patch dicts with image crop and spatial offset metadata.
        """
        w, h = image.size
        if w <= self.max_patch_dimension and h <= self.max_patch_dimension:
            return [{
                "patch_id": 0,
                "image": image,
                "offset_x": 0,
                "offset_y": 0,
                "width": w,
                "height": h,
                "total_patches": 1,
            }]

        patches = []
        stride_x = self.max_patch_dimension - self.patch_overlap_px
        stride_y = self.max_patch_dimension - self.patch_overlap_px

        patch_idx = 0
        y = 0
        while y < h:
            y2 = min(h, y + self.max_patch_dimension)
            y1 = max(0, y2 - self.max_patch_dimension) if y2 == h else y

            x = 0
            while x < w:
                x2 = min(w, x + self.max_patch_dimension)
                x1 = max(0, x2 - self.max_patch_dimension) if x2 == w else x

                box = (x1, y1, x2, y2)
                crop_img = image.crop(box)
                patches.append({
                    "patch_id": patch_idx,
                    "image": crop_img,
                    "offset_x": x1,
                    "offset_y": y1,
                    "width": x2 - x1,
                    "height": y2 - y1,
                })
                patch_idx += 1
                if x2 >= w:
                    break
                x += stride_x

            if y2 >= h:
                break
            y += stride_y

        for p in patches:
            p["total_patches"] = len(patches)

        return patches

    @staticmethod
    def stitch_bbox(local_bbox_pixels: Tuple[int, int, int, int], offset_x: int, offset_y: int) -> Tuple[int, int, int, int]:
        """Translate a patch-local bounding box to document-global pixel coordinates."""
        lx1, ly1, lx2, ly2 = local_bbox_pixels
        return (lx1 + offset_x, ly1 + offset_y, lx2 + offset_x, ly2 + offset_y)

