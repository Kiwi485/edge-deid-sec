# Graph Report - edge-deid-sec  (2026-11-21)

## Corpus Check
- 89 files · ~64,787 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 40 file(s) not represented in the graph (top: .csv 17, .log 7, (none) 3)

## Summary
- 805 nodes · 1683 edges · 49 communities (39 shown, 10 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 24 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `d7ff187f`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_week10_security.py
- cv2
- argparse
- evaluate_batch.py
- load_yolo_bbox
- pipeline_local.py
- shutil
- benchmark_edge.py
- test_web_camera_demo.py
- json
- inference.py
- extraction
- dataset.py
- extraction
- model.py
- acquisition
- observability
- train.py
- x-security
- acquisition
- observability
- TongueSegDataset
- x-security
- volumes
- services
- healthcheck
- build
- healthcheck
- run_final_round.sh
- extraction
- default
- runtime_window.sh
- extraction
- build
- plot_latency.py
- collect_checks.sh
- app.js
- csv
- DemoHandler
- benchmark_vm.py
- args
- services
- services
- camera-run.sh

## God Nodes (most connected - your core abstractions)
1. `run_batch_pipeline()` - 28 edges
2. `load_yolo_bbox()` - 22 edges
3. `extract_features()` - 19 edges
4. `extraction` - 18 edges
5. `extraction` - 18 edges
6. `acquisition` - 18 edges
7. `observability` - 18 edges
8. `acquisition` - 17 edges
9. `observability` - 17 edges
10. `DemoHandler` - 15 edges

## Surprising Connections (you probably didn't know these)
- `main()` --indirect_call--> `handle()`  [INFERRED]
  evidence/security/cis/scripts/build_controls_csv.py → test/test_week10_security.py
- `test_span_hierarchy_and_redacted_exception()` --calls--> `trace_span()`  [EXTRACTED]
  test/test_pipeline_telemetry.py → src/telemetry.py
- `test_disabled_tracing_exports_nothing()` --calls--> `trace_span()`  [EXTRACTED]
  test/test_pipeline_telemetry.py → src/telemetry.py
- `test_invalid_tracing_mode()` --calls--> `trace_span()`  [EXTRACTED]
  test/test_pipeline_telemetry.py → src/telemetry.py
- `test_console_export_is_json()` --calls--> `trace_span()`  [EXTRACTED]
  test/test_pipeline_telemetry.py → src/telemetry.py

## Import Cycles
- None detected.

## Communities (49 total, 10 thin omitted)

### Community 0 - "test_week10_security.py"
Cohesion: 0.08
Nodes (28): build_socket_job(), main(), parse_args(), _percentile(), _handle_job(), main(), handle_socket_job(), parse_args() (+20 more)

### Community 1 - "cv2"
Cohesion: 0.06
Nodes (40): _find_mask(), run_batch_deid(), apply_mask_only(), estimate_tongue_mask(), _find_mask_for_image(), _iter_images(), _largest_component(), main() (+32 more)

### Community 3 - "argparse"
Cohesion: 0.06
Nodes (16): main(), read_tsv(), _load_model(), predict_yolo_bbox(), bbox_to_yolo(), main(), annotate_folder(), main() (+8 more)

### Community 4 - "evaluate_batch.py"
Cohesion: 0.15
Nodes (17): evaluate_privacy(), PrivacyConfig, _safe_ratio(), _to_mask_bool(), _align_to_deid_size(), evaluate_one_bundle(), _find_raw_path(), _fmt_num() (+9 more)

### Community 5 - "load_yolo_bbox"
Cohesion: 0.14
Nodes (3): load_yolo_bbox(), TestErrorCases, TestValidLabel

### Community 6 - "pipeline_local.py"
Cohesion: 0.05
Nodes (29): apply_mask_only(), ensure_dirs(), _load_image(), _normalize_mask(), parse_args(), run_batch_pipeline(), write_csv_header_if_needed(), _write_png() (+21 more)

### Community 7 - "shutil"
Cohesion: 0.16
Nodes (13): main(), parse_args(), _run(), _stub(), test_camera_run_isolates_input_and_checks_results(), test_camera_run_rejects_invalid_web_countdown(), test_pi_camera_compose_preserves_security_and_isolates_mounts(), collect_pairs() (+5 more)

### Community 8 - "benchmark_edge.py"
Cohesion: 0.07
Nodes (25): _benchmark_pipeline(), _benchmark_segmentation(), _device_tree_model(), _environment(), _list_images(), _load_notes(), main(), _package_version() (+17 more)

### Community 9 - "test_web_camera_demo.py"
Cohesion: 0.16
Nodes (13): request(), server(), test_capture_rejects_failed_quality_or_privacy(), test_capture_runs_real_pipeline_contract_and_serves_only_deidentified_image(), fake_pipeline(), test_computer_docker_service_failure_is_not_reported_as_success(), test_computer_webcam_uses_docker_and_validates_output(), fake_docker() (+5 more)

### Community 10 - "json"
Cohesion: 0.11
Nodes (22): build_report_text(), _counter_block(), _get_raw_stems(), _load_metas(), main(), _pct(), build_validation_rows(), _check_csv() (+14 more)

### Community 11 - "inference.py"
Cohesion: 0.17
Nodes (5): _get_model(), main(), _preprocess(), run_inference(), get_device()

### Community 12 - "extraction"
Cohesion: 0.12
Nodes (17): EDGE_DEID_TRACING, cap_drop, command, container_name, cpu_shares, cpus, environment, mem_limit (+9 more)

### Community 13 - "dataset.py"
Cohesion: 0.16
Nodes (4): build_coco_sample_list(), load_image_rgb(), polygon_to_mask(), yolo_bbox_to_mask()

### Community 14 - "extraction"
Cohesion: 0.12
Nodes (16): EDGE_DEID_TRACING, cap_drop, command, container_name, cpu_shares, cpus, environment, mem_limit (+8 more)

### Community 15 - "model.py"
Cohesion: 0.19
Nodes (5): build_model(), build_model_by_arch(), build_model_deeplabv3(), build_model_unet_resnet(), main()

### Community 16 - "acquisition"
Cohesion: 0.13
Nodes (15): build, cap_drop, command, container_name, cpu_shares, cpus, mem_limit, pids_limit (+7 more)

### Community 17 - "observability"
Cohesion: 0.13
Nodes (15): build, cap_drop, command, container_name, cpu_shares, cpus, mem_limit, pids_limit (+7 more)

### Community 18 - "train.py"
Cohesion: 0.23
Nodes (8): count_parameters(), build_datasets(), dice_score(), _indices_from_manifest(), iou_score(), main(), train_epoch(), val_epoch()

### Community 19 - "x-security"
Cohesion: 0.15
Nodes (12): name, name, services, volumes, ipc, x-security, cap_drop, pids_limit (+4 more)

### Community 20 - "acquisition"
Cohesion: 0.15
Nodes (13): cap_drop, command, container_name, cpu_shares, cpus, mem_limit, pids_limit, read_only (+5 more)

### Community 21 - "observability"
Cohesion: 0.15
Nodes (13): cap_drop, command, container_name, cpu_shares, cpus, mem_limit, pids_limit, read_only (+5 more)

### Community 23 - "x-security"
Cohesion: 0.18
Nodes (10): services, volumes, ipc, x-security, cap_drop, pids_limit, read_only, security_opt (+2 more)

### Community 24 - "volumes"
Cohesion: 0.40
Nodes (10): volumes, selinux, volumes, volumes, bind, read_only, source, target (+2 more)

### Community 25 - "services"
Cohesion: 0.25
Nodes (7): volumes, security_opt, volumes, services, acquisition, extraction, observability

### Community 26 - "healthcheck"
Cohesion: 0.57
Nodes (7): healthcheck, healthcheck, interval, retries, test, timeout, healthcheck

### Community 27 - "build"
Cohesion: 0.38
Nodes (7): build, INSTALL_TFLITE, args, context, dockerfile, build, build

### Community 28 - "healthcheck"
Cohesion: 0.57
Nodes (7): healthcheck, healthcheck, interval, retries, test, timeout, healthcheck

### Community 29 - "run_final_round.sh"
Cohesion: 0.33
Nodes (5): BATCH_LIMIT, INSTALL_TFLITE, SEG_BACKEND, run_final_round.sh script, step()

### Community 30 - "extraction"
Cohesion: 0.40
Nodes (5): depends_on, extraction, condition, required, depends_on

### Community 31 - "default"
Cohesion: 0.40
Nodes (5): networks, name, networks, default, networks

### Community 32 - "runtime_window.sh"
Cohesion: 0.40
Nodes (4): BATCH_LIMIT, INSTALL_TFLITE, SEG_BACKEND, runtime_window.sh script

### Community 33 - "extraction"
Cohesion: 0.50
Nodes (4): depends_on, extraction, condition, depends_on

### Community 34 - "build"
Cohesion: 0.50
Nodes (4): INSTALL_TFLITE, args, context, build

### Community 38 - "app.js"
Cohesion: 0.11
Nodes (19): cameraState, captureButton, countdown, countdownInput, initialize(), milliseconds(), placeholder, preview (+11 more)

### Community 39 - "csv"
Cohesion: 0.23
Nodes (12): annotation_files(), extract_roi(), find_image(), infer_split(), load_coco_records(), load_image(), load_split_manifest(), main() (+4 more)

### Community 41 - "benchmark_vm.py"
Cohesion: 0.29
Nodes (9): bottleneck_text(), compute_percentiles(), format_table(), load_rows(), main(), parse_args(), Row, _to_float() (+1 more)

### Community 42 - "args"
Cohesion: 0.24
Nodes (10): build, PI_ARM64, args, context, build, build, services, acquisition (+2 more)

### Community 43 - "services"
Cohesion: 0.25
Nodes (7): volumes, volumes, volumes, services, acquisition, extraction, observability

### Community 44 - "services"
Cohesion: 0.25
Nodes (7): container_name, container_name, container_name, services, acquisition, extraction, observability

## Knowledge Gaps
- **6 isolated node(s):** `BATCH_LIMIT`, `INSTALL_TFLITE`, `SEG_BACKEND`, `BATCH_LIMIT`, `INSTALL_TFLITE` (+1 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 294 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **10 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `load_yolo_bbox()` connect `load_yolo_bbox` to `argparse`, `pipeline_local.py`?**
  _High betweenness centrality (0.028) - this node is a cross-community bridge._
- **What connects `BATCH_LIMIT`, `INSTALL_TFLITE`, `SEG_BACKEND` to the rest of the system?**
  _6 weakly-connected nodes found - possible missing edges._
- **Should `test_week10_security.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07826694619147449 - nodes in this community are weakly interconnected._
- **Why does `DemoHandler` connect `DemoHandler` to `argparse`?**
  _High betweenness centrality (0.024) - this node is a cross-community bridge._
- **Should `cv2` be split into smaller, more focused modules?**
  _Cohesion score 0.06052393857271906 - nodes in this community are weakly interconnected._
- **Why does `run_batch_pipeline()` connect `pipeline_local.py` to `test_week10_security.py`, `cv2`, `argparse`, `evaluate_batch.py`, `shutil`, `benchmark_edge.py`, `csv`, `json`, `inference.py`?**
  _High betweenness centrality (0.021) - this node is a cross-community bridge._
- **Should `argparse` be split into smaller, more focused modules?**
  _Cohesion score 0.06184012066365008 - nodes in this community are weakly interconnected._