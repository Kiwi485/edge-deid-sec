# Graph Report - edge-deid-sec  (2026-11-05)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 698 nodes · 1504 edges · 38 communities (34 shown, 4 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 16 edges (avg confidence: 0.86)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `1602bb91`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Community 0
- Community 1
- Community 2
- Community 3
- Community 4
- Community 5
- Community 6
- Community 7
- Community 8
- Community 9
- Community 10
- Community 11
- Community 12
- Community 13
- Community 14
- Community 15
- Community 16
- Community 17
- Community 18
- Community 19
- Community 20
- Community 21
- Community 22
- Community 23
- Community 24
- Community 25
- Community 26
- Community 27
- Community 28
- Community 29
- Community 30
- Community 31
- Community 32
- Community 33
- Community 34
- Community 35
- Community 36

## God Nodes (most connected - your core abstractions)
1. `run_batch_pipeline()` - 27 edges
2. `load_yolo_bbox()` - 22 edges
3. `extract_features()` - 19 edges
4. `extraction` - 18 edges
5. `extraction` - 18 edges
6. `acquisition` - 18 edges
7. `observability` - 18 edges
8. `acquisition` - 17 edges
9. `observability` - 17 edges
10. `run_inference()` - 15 edges

## Surprising Connections (you probably didn't know these)
- `main()` --calls--> `build_model_by_arch()`  [EXTRACTED]
  tools/export_seg_tflite.py → src/seg/model.py
- `handle()` --calls--> `_handle_job()`  [EXTRACTED]
  test/test_week10_security.py → src/services/extraction_service.py
- `test_send_and_serve_job_roundtrip()` --indirect_call--> `serve_jobs()`  [INFERRED]
  test/test_unix_socket_ipc.py → src/services/ipc.py
- `test_image_content_roundtrip_over_socket()` --indirect_call--> `serve_jobs()`  [INFERRED]
  test/test_week10_security.py → src/services/ipc.py
- `test_interpreter_receives_explicit_thread_count()` --calls--> `_load_interpreter()`  [EXTRACTED]
  test/test_tflite_inference.py → src/seg/tflite_inference.py

## Import Cycles
- None detected.

## Communities (38 total, 4 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.07
Nodes (30): build_socket_job(), main(), parse_args(), _percentile(), _handle_job(), main(), handle_socket_job(), parse_args() (+22 more)

### Community 1 - "Community 1"
Cohesion: 0.08
Nodes (32): apply_mask_only(), estimate_tongue_mask(), _find_mask_for_image(), _iter_images(), _largest_component(), main(), run_batch(), _crop_to_bbox() (+24 more)

### Community 2 - "Community 2"
Cohesion: 0.05
Nodes (19): _console_tracer(), _get_tracer(), trace_span(), bbox_to_yolo(), main(), assert_no_sensitive_trace_data(), exported_spans(), pipeline_case() (+11 more)

### Community 3 - "Community 3"
Cohesion: 0.08
Nodes (21): main(), read_tsv(), _load_model(), predict_yolo_bbox(), handle(), annotation_files(), extract_roi(), find_image() (+13 more)

### Community 4 - "Community 4"
Cohesion: 0.10
Nodes (26): bottleneck_text(), compute_percentiles(), format_table(), load_rows(), main(), parse_args(), Row, _to_float() (+18 more)

### Community 5 - "Community 5"
Cohesion: 0.09
Nodes (7): load_yolo_bbox(), annotate_folder(), main(), to_yolo_norm(), TestErrorCases, TestValidLabel, main()

### Community 6 - "Community 6"
Cohesion: 0.11
Nodes (13): apply_mask_only(), ensure_dirs(), _load_image(), _normalize_mask(), run_batch_pipeline(), write_csv_header_if_needed(), check_quality(), extract_roi_fixed() (+5 more)

### Community 7 - "Community 7"
Cohesion: 0.14
Nodes (12): parse_args(), convert(), main(), polygon_bbox(), to_yolo_bbox(), collect_pairs(), copy_split(), main() (+4 more)

### Community 8 - "Community 8"
Cohesion: 0.14
Nodes (18): _benchmark_pipeline(), _benchmark_segmentation(), _device_tree_model(), _environment(), _list_images(), _load_notes(), main(), _package_version() (+10 more)

### Community 9 - "Community 9"
Cohesion: 0.14
Nodes (11): _find_mask(), run_batch_deid(), build_mask(), _clip_bbox(), _load_json(), main(), process_bundle(), run_batch() (+3 more)

### Community 10 - "Community 10"
Cohesion: 0.16
Nodes (18): build_report_text(), _counter_block(), _get_raw_stems(), _load_metas(), main(), _pct(), build_validation_rows(), _check_csv() (+10 more)

### Community 11 - "Community 11"
Cohesion: 0.17
Nodes (5): _get_model(), main(), _preprocess(), run_inference(), get_device()

### Community 12 - "Community 12"
Cohesion: 0.12
Nodes (17): EDGE_DEID_TRACING, cap_drop, command, container_name, cpu_shares, cpus, environment, mem_limit (+9 more)

### Community 13 - "Community 13"
Cohesion: 0.16
Nodes (4): build_coco_sample_list(), load_image_rgb(), polygon_to_mask(), yolo_bbox_to_mask()

### Community 14 - "Community 14"
Cohesion: 0.12
Nodes (16): EDGE_DEID_TRACING, cap_drop, command, container_name, cpu_shares, cpus, environment, mem_limit (+8 more)

### Community 15 - "Community 15"
Cohesion: 0.19
Nodes (5): build_model(), build_model_by_arch(), build_model_deeplabv3(), build_model_unet_resnet(), main()

### Community 16 - "Community 16"
Cohesion: 0.13
Nodes (15): build, cap_drop, command, container_name, cpu_shares, cpus, mem_limit, pids_limit (+7 more)

### Community 17 - "Community 17"
Cohesion: 0.13
Nodes (15): build, cap_drop, command, container_name, cpu_shares, cpus, mem_limit, pids_limit (+7 more)

### Community 18 - "Community 18"
Cohesion: 0.23
Nodes (8): count_parameters(), build_datasets(), dice_score(), _indices_from_manifest(), iou_score(), main(), train_epoch(), val_epoch()

### Community 19 - "Community 19"
Cohesion: 0.15
Nodes (12): name, name, services, volumes, ipc, x-security, cap_drop, pids_limit (+4 more)

### Community 20 - "Community 20"
Cohesion: 0.15
Nodes (13): cap_drop, command, container_name, cpu_shares, cpus, mem_limit, pids_limit, read_only (+5 more)

### Community 21 - "Community 21"
Cohesion: 0.15
Nodes (13): cap_drop, command, container_name, cpu_shares, cpus, mem_limit, pids_limit, read_only (+5 more)

### Community 23 - "Community 23"
Cohesion: 0.18
Nodes (10): services, volumes, ipc, x-security, cap_drop, pids_limit, read_only, security_opt (+2 more)

### Community 24 - "Community 24"
Cohesion: 0.40
Nodes (10): volumes, selinux, volumes, volumes, bind, read_only, source, target (+2 more)

### Community 25 - "Community 25"
Cohesion: 0.25
Nodes (7): volumes, security_opt, volumes, services, acquisition, extraction, observability

### Community 26 - "Community 26"
Cohesion: 0.57
Nodes (7): healthcheck, healthcheck, interval, retries, test, timeout, healthcheck

### Community 27 - "Community 27"
Cohesion: 0.38
Nodes (7): build, INSTALL_TFLITE, args, context, dockerfile, build, build

### Community 28 - "Community 28"
Cohesion: 0.57
Nodes (7): healthcheck, healthcheck, interval, retries, test, timeout, healthcheck

### Community 29 - "Community 29"
Cohesion: 0.33
Nodes (5): BATCH_LIMIT, INSTALL_TFLITE, SEG_BACKEND, run_final_round.sh script, step()

### Community 30 - "Community 30"
Cohesion: 0.40
Nodes (5): depends_on, extraction, condition, required, depends_on

### Community 31 - "Community 31"
Cohesion: 0.40
Nodes (5): networks, name, networks, default, networks

### Community 32 - "Community 32"
Cohesion: 0.40
Nodes (4): BATCH_LIMIT, INSTALL_TFLITE, SEG_BACKEND, runtime_window.sh script

### Community 33 - "Community 33"
Cohesion: 0.50
Nodes (4): depends_on, extraction, condition, depends_on

### Community 34 - "Community 34"
Cohesion: 0.50
Nodes (4): INSTALL_TFLITE, args, context, build

## Knowledge Gaps
- **6 isolated node(s):** `BATCH_LIMIT`, `INSTALL_TFLITE`, `SEG_BACKEND`, `BATCH_LIMIT`, `INSTALL_TFLITE` (+1 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 250 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `load_yolo_bbox()` connect `Community 5` to `Community 6`?**
  _High betweenness centrality (0.035) - this node is a cross-community bridge._
- **What connects `BATCH_LIMIT`, `INSTALL_TFLITE`, `SEG_BACKEND` to the rest of the system?**
  _6 weakly-connected nodes found - possible missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.07103825136612021 - nodes in this community are weakly interconnected._
- **Why does `run_batch_pipeline()` connect `Community 6` to `Community 0`, `Community 1`, `Community 2`, `Community 3`, `Community 4`, `Community 7`, `Community 8`, `Community 9`, `Community 10`, `Community 11`?**
  _High betweenness centrality (0.024) - this node is a cross-community bridge._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.08469945355191257 - nodes in this community are weakly interconnected._
- **Why does `TongueSegDataset` connect `Community 22` to `Community 18`, `Community 13`?**
  _High betweenness centrality (0.013) - this node is a cross-community bridge._
- **Should `Community 2` be split into smaller, more focused modules?**
  _Cohesion score 0.05333333333333334 - nodes in this community are weakly interconnected._