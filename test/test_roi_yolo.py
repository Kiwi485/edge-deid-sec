"""Unit tests for src/roi/roi_yolo.py load_yolo_bbox()."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.roi.roi_yolo import load_yolo_bbox

# Reusable image shape (H=300, W=400, C=3)
SHAPE = (300, 400, 3)
H, W = 300, 400


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------

class TestValidLabel:
    def test_returns_ok_status(self, tmp_path):
        label = tmp_path / "img.txt"
        label.write_text("0 0.5 0.65 0.55 0.35\n")
        _, status, error = load_yolo_bbox(label, SHAPE)
        assert status == "ok"
        assert error == ""

    def test_bbox_has_four_ints(self, tmp_path):
        label = tmp_path / "img.txt"
        label.write_text("0 0.5 0.65 0.55 0.35\n")
        bbox, status, _ = load_yolo_bbox(label, SHAPE)
        assert status == "ok"
        assert len(bbox) == 4
        assert all(isinstance(v, int) for v in bbox)

    def test_bbox_within_image_bounds(self, tmp_path):
        label = tmp_path / "img.txt"
        label.write_text("0 0.5 0.65 0.55 0.35\n")
        bbox, status, _ = load_yolo_bbox(label, SHAPE)
        x1, y1, x2, y2 = bbox
        assert 0 <= x1 < x2 <= W
        assert 0 <= y1 < y2 <= H

    def test_pixel_values_correct(self, tmp_path):
        """xc=0.5 w=0.5 on W=400 => x1=100, x2=300."""
        label = tmp_path / "img.txt"
        label.write_text("0 0.5 0.5 0.5 0.5\n")
        bbox, status, _ = load_yolo_bbox(label, SHAPE)
        assert status == "ok"
        x1, y1, x2, y2 = bbox
        assert x1 == 100
        assert x2 == 300
        assert y1 == 75
        assert y2 == 225

    def test_only_first_line_used(self, tmp_path):
        """Multiple lines: only the first bbox is returned."""
        label = tmp_path / "multi.txt"
        label.write_text("0 0.5 0.5 0.5 0.5\n1 0.2 0.2 0.1 0.1\n")
        bbox, status, _ = load_yolo_bbox(label, SHAPE)
        assert status == "ok"
        assert bbox == [100, 75, 300, 225]

    def test_accepts_tuple_shape(self, tmp_path):
        label = tmp_path / "img.txt"
        label.write_text("0 0.5 0.5 0.4 0.4\n")
        _, status, _ = load_yolo_bbox(label, (300, 400))
        assert status == "ok"

    def test_bbox_clamped_when_near_edge(self, tmp_path):
        """xc=0.05 bw=0.5 => raw x1 would be negative; must clamp to 0."""
        label = tmp_path / "edge.txt"
        label.write_text("0 0.05 0.5 0.5 0.5\n")
        bbox, status, _ = load_yolo_bbox(label, SHAPE)
        assert status == "ok"
        x1, _, x2, _ = bbox
        assert x1 >= 0
        assert x1 < x2


# ---------------------------------------------------------------------------
# Error-path tests
# ---------------------------------------------------------------------------

class TestErrorCases:
    def test_file_not_found(self, tmp_path):
        bbox, status, error = load_yolo_bbox(tmp_path / "missing.txt", SHAPE)
        assert status == "error"
        assert bbox == []
        assert "not found" in error

    def test_empty_file(self, tmp_path):
        label = tmp_path / "empty.txt"
        label.write_text("   \n\n")
        bbox, status, error = load_yolo_bbox(label, SHAPE)
        assert status == "error"
        assert bbox == []
        assert "empty" in error

    def test_too_few_fields(self, tmp_path):
        label = tmp_path / "short.txt"
        label.write_text("0 0.5 0.5\n")
        bbox, status, error = load_yolo_bbox(label, SHAPE)
        assert status == "error"
        assert "5 fields" in error

    def test_too_many_fields(self, tmp_path):
        label = tmp_path / "long.txt"
        label.write_text("0 0.5 0.5 0.5 0.5 extra\n")
        bbox, status, error = load_yolo_bbox(label, SHAPE)
        assert status == "error"

    def test_non_numeric_value(self, tmp_path):
        label = tmp_path / "nan.txt"
        label.write_text("0 abc 0.5 0.5 0.5\n")
        bbox, status, error = load_yolo_bbox(label, SHAPE)
        assert status == "error"
        assert "non-numeric" in error

    def test_x_center_out_of_range(self, tmp_path):
        label = tmp_path / "oor.txt"
        label.write_text("0 1.5 0.5 0.5 0.5\n")
        bbox, status, error = load_yolo_bbox(label, SHAPE)
        assert status == "error"
        assert "xc" in error

    def test_negative_value(self, tmp_path):
        label = tmp_path / "neg.txt"
        label.write_text("0 0.5 -0.1 0.5 0.5\n")
        bbox, status, error = load_yolo_bbox(label, SHAPE)
        assert status == "error"

    def test_invalid_image_shape_zero(self, tmp_path):
        label = tmp_path / "img.txt"
        label.write_text("0 0.5 0.5 0.5 0.5\n")
        bbox, status, error = load_yolo_bbox(label, (0, 400, 3))
        assert status == "error"
        assert "image_shape" in error
