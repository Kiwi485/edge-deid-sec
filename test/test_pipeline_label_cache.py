"""Regression tests for pseudo-label persistence in the local pipeline."""

from src.pipeline_local import should_cache_yolo_label


def test_fixed_crop_is_never_saved_as_a_yolo_label():
    assert not should_cache_yolo_label("fixed_fallback", "ok")


def test_successful_yolo_detection_can_be_saved_as_a_pseudo_label():
    assert should_cache_yolo_label("yolo_detect", "ok")


def test_failed_or_quality_rejected_images_do_not_create_labels():
    assert not should_cache_yolo_label("yolo_detect", "quality_fail")
    assert not should_cache_yolo_label("yolo_detect", "error")
