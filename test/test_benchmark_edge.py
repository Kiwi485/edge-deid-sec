import csv

import pytest

from src import benchmark_edge
from src.benchmark_edge import summarize_latencies


def test_summarize_latencies_reports_mean_spread_percentiles_and_fps():
    result = summarize_latencies([10.0, 20.0, 30.0])

    assert result["n"] == 3
    assert result["mean_ms"] == pytest.approx(20.0)
    assert result["stddev_ms"] == pytest.approx(8.1649658)
    assert result["median_ms"] == pytest.approx(20.0)
    assert result["p95_ms"] == pytest.approx(29.0)
    assert result["fps_from_mean"] == pytest.approx(50.0)


def test_summarize_latencies_rejects_empty_input():
    with pytest.raises(ValueError, match="empty"):
        summarize_latencies([])


def test_pipeline_image_selection_includes_heic_in_sorted_limit(tmp_path):
    for name in ("b.JPG", "a.HEIC", "c.png"):
        (tmp_path / name).touch()

    selected = benchmark_edge._list_images(tmp_path, 2, include_heic=True)

    assert [path.name for path in selected] == ["a.HEIC", "b.JPG"]
    assert [path.name for path in benchmark_edge._list_images(tmp_path, 2)] == [
        "b.JPG", "c.png",
    ]


def test_benchmark_rejects_fewer_images_than_requested(tmp_path, monkeypatch, capsys):
    (tmp_path / "image.jpg").touch()
    model = tmp_path / "model.tflite"
    model.touch()
    output = tmp_path / "result"
    monkeypatch.setattr(benchmark_edge.sys, "platform", "linux")
    monkeypatch.setattr(benchmark_edge.sys, "argv", [
        "benchmark_edge.py", "--mode", "pipeline", "--input-dir", str(tmp_path),
        "--model", str(model), "--output-dir", str(output), "--limit", "2",
    ])

    with pytest.raises(SystemExit) as exc:
        benchmark_edge.main()

    assert exc.value.code == 2
    assert "Requested 2 input images; found only 1." in capsys.readouterr().err
    assert not output.exists()


def test_pipeline_decodes_heic_and_uses_selected_images_for_every_run(tmp_path, monkeypatch):
    pillow_heif = pytest.importorskip("pillow_heif")
    image = pytest.importorskip("PIL.Image")
    from src import pipeline_local
    from src.seg import tflite_inference

    heic = tmp_path / "a.HEIC"
    pillow_heif.from_pillow(image.new("RGB", (8, 8), (120, 80, 40))).save(heic)
    jpgs = [tmp_path / f"b{index:03d}.jpg" for index in range(99)]
    for jpg in jpgs:
        jpg.touch()
    (tmp_path / "c.png").touch()
    selected = [heic, *jpgs]
    calls = []

    def fake_inference(*args, **kwargs):
        assert kwargs["image_array"].shape == (8, 8, 3)
        return None, None, {"model_load_ms": 1.0}

    def fake_batch(**kwargs):
        calls.append(kwargs)
        assert kwargs["image_names"] == {path.name for path in selected}
        count = min(kwargs["limit"], len(kwargs["image_names"]))
        fields = ["status", "total_ms", *benchmark_edge.PIPELINE_TIMING_FIELDS]
        kwargs["csv_path"].parent.mkdir(parents=True, exist_ok=True)
        with kwargs["csv_path"].open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for _ in range(count):
                writer.writerow({**{field: 1.0 for field in fields}, "status": "ok"})

    monkeypatch.setattr(tflite_inference, "run_inference", fake_inference)
    monkeypatch.setattr(pipeline_local, "run_batch_pipeline", fake_batch)

    rows, cold_load_ms = benchmark_edge._benchmark_pipeline(
        selected, tmp_path, tmp_path / "model.tflite", warmups=10, runs=3, threads=1,
    )

    assert cold_load_ms == 1.0
    assert [call["limit"] for call in calls] == [10, 100, 100, 100]
    assert len(rows) == 300
    assert [row["run"] for row in rows] == [1] * 100 + [2] * 100 + [3] * 100
