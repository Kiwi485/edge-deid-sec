# Project Context (READ FIRST)

Project: EdgeTongueDX – Year 1 Feasibility Study

Goal:
This project is for a first-year undergraduate research proposal.
The goal is NOT medical diagnosis accuracy.
The goal is to prove system feasibility on low-resource environments.

What the code should do:
- Capture webcam frames
- Detect mouth / tongue ROI (simple bounding box is enough)
- Measure per-frame latency (ms)
- Measure FPS
- Measure CPU and RAM usage
- Output logs (CSV or TXT)

Constraints:
- No model training
- No dataset collection
- No Raspberry Pi required at this stage
- VM is used to simulate low CPU / RAM environments

Evaluation focus:
- Latency
- FPS
- CPU usage
- Memory usage

Important:
Keep the code minimal. Avoid unnecessary features.
