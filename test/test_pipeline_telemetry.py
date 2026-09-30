import csv
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import cv2
import numpy as np
import pytest
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from src import telemetry


@pytest.fixture
def exported_spans(monkeypatch):
    exporter = InMemorySpanExporter()
    provider = TracerProvider(resource=Resource({"service.name": "test"}))
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setenv("EDGE_DEID_TRACING", "console")
    monkeypatch.setattr(telemetry, "_console_tracer", lambda: provider.get_tracer("test"))
    yield exporter
    provider.shutdown()


def test_span_hierarchy_and_redacted_exception(exported_spans):
    secret = "/private/patient-name/photo.png"
    with telemetry.trace_span("total"):
        with pytest.raises(ValueError):
            with telemetry.trace_span("seg"):
                raise ValueError(secret)

    child, parent = exported_spans.get_finished_spans()
    assert child.parent.span_id == parent.context.span_id
    assert child.context.trace_id == parent.context.trace_id
    assert parent.start_time <= child.start_time <= child.end_time <= parent.end_time
    assert child.status.status_code == StatusCode.ERROR
    assert parent.status.status_code == StatusCode.OK
    assert child.events == ()
    assert secret not in child.to_json()


def test_disabled_tracing_exports_nothing(exported_spans, monkeypatch):
    monkeypatch.delenv("EDGE_DEID_TRACING")
    with telemetry.trace_span("total") as span:
        assert not span.is_recording()
    assert not exported_spans.get_finished_spans()


def test_invalid_tracing_mode(monkeypatch):
    monkeypatch.setenv("EDGE_DEID_TRACING", "invalid")
    with pytest.raises(ValueError, match="off or console"):
        with telemetry.trace_span("total"):
            pass


def test_console_export_is_json(monkeypatch, capsys):
    monkeypatch.setenv("EDGE_DEID_TRACING", "console")
    telemetry._console_tracer.cache_clear()
    try:
        with telemetry.trace_span("total", seg_backend="tflite"):
            pass
        payload = json.loads(capsys.readouterr().out)
        assert payload["name"] == "total"
        assert payload["attributes"] == {"seg_backend": "tflite"}
        assert payload["status"]["status_code"] == "OK"
        assert payload["resource"]["attributes"] == {"service.name": "edge-deid-extraction"}
    finally:
        telemetry._console_tracer.cache_clear()


@pytest.fixture
def pipeline_case(monkeypatch, tmp_path):
    def roi_result(image):
        height, width = image.shape[:2]
        return image[2:-2, 2:-2], (2, 2, width - 2, height - 2), "ok", ""

    replacements = {
        "roi_mediapipe": {"extract_roi_mediapipe": roi_result},
        "roi_yolo_detect": {"predict_yolo_bbox": roi_result},
        "roi_fixed_crop": {"extract_roi_fixed": lambda image: roi_result(image)[:2]},
        "quality_check": {"check_quality": lambda image: {"pass": True, "reason": "", "metrics": {}}},
    }
    for module_name, members in replacements.items():
        for prefix in ("roi", "src.roi"):
            module = ModuleType(f"{prefix}.{module_name}")
            module.__dict__.update(members)
            monkeypatch.setitem(sys.modules, module.__name__, module)

    def infer(*args, image_array, **kwargs):
        mask = np.zeros(image_array.shape[:2], dtype=np.uint8)
        mask[2:-2, 2:-2] = 255
        return mask, image_array, {
            "model_load_ms": 0.0, "seg_preprocess_ms": 0.0, "seg_forward_ms": 0.0,
        }

    backends = {}
    for backend, module_name in (("torch", "inference"), ("tflite", "tflite_inference")):
        module = ModuleType(f"src.seg.{module_name}")
        module.run_inference = infer
        monkeypatch.setitem(sys.modules, module.__name__, module)
        backends[backend] = module

    source = Path(__file__).resolve().parents[1] / "src" / "pipeline_local.py"
    spec = importlib.util.spec_from_file_location("_pipeline_telemetry_test", source)
    pipeline = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pipeline)
    monkeypatch.setattr(pipeline, "trace_span", telemetry.trace_span)
    monkeypatch.setattr(pipeline, "RESIZE_TO", None)

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    image = np.full((24, 24, 3), 160, dtype=np.uint8)
    assert cv2.imwrite(str(raw_dir / "patient-sensitive.png"), image)
    model_path = tmp_path / "patient-model.pth"
    model_path.touch()
    return SimpleNamespace(
        pipeline=pipeline,
        backends=backends,
        kwargs={
            "raw_dir": raw_dir,
            "out_dir": tmp_path / "out",
            "csv_path": tmp_path / "latency.csv",
            "seg_model_path": model_path,
        },
    )


def assert_no_sensitive_trace_data(spans, tmp_path):
    for span in spans:
        payload = span.to_json()
        assert "patient-sensitive" not in payload
        assert "patient-model" not in payload
        assert str(tmp_path) not in payload
        assert not span.events


@pytest.mark.parametrize("backend", ["torch", "tflite"])
def test_pipeline_spans_and_unchanged_outputs(pipeline_case, exported_spans, monkeypatch, tmp_path, backend):
    pipeline_case.pipeline.run_batch_pipeline(**pipeline_case.kwargs, seg_backend=backend)
    spans = exported_spans.get_finished_spans()
    assert [span.name for span in spans] == ["roi", "seg", "feat", "deid", "privacy", "total"]
    parent = spans[-1]
    assert parent.parent is None
    assert parent.attributes["seg_backend"] == backend
    assert parent.attributes["feature_version"] == "v2_glcm"
    assert parent.attributes["pipeline.status"] == "ok"
    assert parent.attributes["privacy.pass"] is True
    for child in spans[:-1]:
        assert child.parent.span_id == parent.context.span_id
        assert child.context.trace_id == parent.context.trace_id
        assert parent.start_time <= child.start_time <= child.end_time <= parent.end_time
    assert all(span.status.status_code == StatusCode.OK for span in spans)
    assert_no_sensitive_trace_data(spans, tmp_path)

    output = pipeline_case.kwargs["out_dir"] / "patient-sensitive"
    vector = np.load(output / "feature_256.npy")
    mask = cv2.imread(str(output / "mask.png"))
    deid = cv2.imread(str(output / "deid.png"))
    metadata = json.loads((output / "meta.json").read_text())
    assert vector.shape == (256,) and vector.dtype == np.float32
    assert np.isfinite(vector).all()
    assert metadata["status"] == "ok" and metadata["feature_version"] == "v2_glcm"
    assert metadata["privacy_metrics"]["privacy_pass"] is True
    assert all(metadata["timing_ms"][f"{name}_ms"] >= 0 for name in ("roi", "seg", "feat", "deid", "privacy", "total"))
    with pipeline_case.kwargs["csv_path"].open() as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 1 and rows[0]["status"] == "ok"

    exported_spans.clear()
    monkeypatch.setenv("EDGE_DEID_TRACING", "off")
    pipeline_case.pipeline.run_batch_pipeline(**pipeline_case.kwargs, seg_backend=backend)
    assert not exported_spans.get_finished_spans()
    np.testing.assert_array_equal(np.load(output / "feature_256.npy"), vector)
    np.testing.assert_array_equal(cv2.imread(str(output / "mask.png")), mask)
    np.testing.assert_array_equal(cv2.imread(str(output / "deid.png")), deid)


@pytest.mark.parametrize("separate_calls", [False, True])
def test_each_image_has_its_own_trace(pipeline_case, exported_spans, separate_calls):
    if separate_calls:
        pipeline_case.pipeline.run_batch_pipeline(**pipeline_case.kwargs)
        pipeline_case.pipeline.run_batch_pipeline(**pipeline_case.kwargs)
    else:
        raw_dir = pipeline_case.kwargs["raw_dir"]
        (raw_dir / "second.png").write_bytes((raw_dir / "patient-sensitive.png").read_bytes())
        pipeline_case.pipeline.run_batch_pipeline(**pipeline_case.kwargs)
    spans = exported_spans.get_finished_spans()
    roots = [span for span in spans if span.name == "total"]
    assert len(spans) == 12 and len(roots) == 2
    assert all(span.parent is None for span in roots)
    assert roots[0].context.trace_id != roots[1].context.trace_id


@pytest.mark.parametrize("failure", ["roi", "seg", "missing_model", "feat", "deid", "privacy", "privacy_reject", "quality", "load"])
def test_pipeline_failure_spans(pipeline_case, exported_spans, monkeypatch, tmp_path, failure):
    def fail(*args, **kwargs):
        raise RuntimeError(f"patient-sensitive {tmp_path}")

    functions = {"roi": "extract_roi_mediapipe", "feat": "extract_features", "deid": "deid_mask_only", "privacy": "evaluate_privacy", "load": "_load_image"}
    if failure in functions:
        monkeypatch.setattr(pipeline_case.pipeline, functions[failure], fail)
    elif failure == "seg":
        monkeypatch.setattr(pipeline_case.backends["torch"], "run_inference", fail)
    elif failure == "missing_model":
        pipeline_case.kwargs["seg_model_path"].unlink()
    elif failure == "privacy_reject":
        monkeypatch.setattr(pipeline_case.pipeline, "evaluate_privacy", lambda *args, **kwargs: {"privacy_pass": False})
    elif failure == "quality":
        monkeypatch.setattr(pipeline_case.pipeline, "check_quality", lambda image: {"pass": False, "reason": "patient-sensitive", "metrics": {}})

    pipeline_case.pipeline.run_batch_pipeline(**pipeline_case.kwargs)
    spans = exported_spans.get_finished_spans()
    by_name = {span.name: span for span in spans}
    assert by_name["total"].status.status_code == StatusCode.ERROR
    if failure not in {"load", "quality"}:
        stage = {"privacy_reject": "privacy", "missing_model": "seg"}.get(failure, failure)
        assert by_name[stage].status.status_code == StatusCode.ERROR
        stage_names = ["roi", "seg", "feat", "deid", "privacy"]
        assert [span.name for span in spans] == stage_names[:stage_names.index(stage) + 1] + ["total"]
    expected_status = "ok" if failure.startswith("privacy") else "quality_fail" if failure == "quality" else "error"
    assert by_name["total"].attributes["pipeline.status"] == expected_status
    assert_no_sensitive_trace_data(spans, tmp_path)
    output = pipeline_case.kwargs["out_dir"] / "patient-sensitive"
    assert json.loads((output / "meta.json").read_text())["status"] == expected_status