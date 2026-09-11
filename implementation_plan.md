# Implementation Plan: Adaptive Micro-Assembly Inspector (AMAI)

## Project Overview
**Adaptive Micro-Assembly Inspector (AMAI)** is an end-to-end, simulation-first Physical AI micro-assembly quality assurance and robotic sorting system built for the **AI Infra Summit Hackathon** (competing in Intel Robotics *Physical AI Challenge* and Speechmatics *Best Use of Speechmatics* bonus award).

The system integrates:
1. **Simulation**: Pure-Python PyBullet environment simulating a 6-DoF SO-101/SO-ARM100 robotic arm with a parallel gripper, procedural PCB defect generation, and calibrated overhead RGB-D camera.
2. **Edge AI Inference**: Intel OpenVINO model runner executing fast (<30ms) surface defect detection and 2D-to-3D projection.
3. **VLA Motion Planning**: Kinematics & affordance planner calculating keep-out zones and generating smooth trajectory waypoints to sort PCBs into Pass vs. Scrap/Rework bins.
4. **Voice Agent Oversight**: Speechmatics streaming client & intent parser with an immutable SQLite/JSON audit trail.
5. **Interactive Operations UI**: A high-aesthetic Streamlit dashboard with live PyBullet visualization, telemetry, and manual/voice override triggers.
6. **Hackathon Submission Collateral**: Production test harness, submission metadata, 6-slide deck outline, and 3-minute video pitch script.

---

## User Review Required

> [!IMPORTANT]
> - **Self-Contained & Zero External Keys Required**: The system supports live API connections (Speechmatics & OpenVINO hardware targets) while providing automated zero-key mock/fallback modes so any judge or CI runner can clone and test 100% of features locally.
> - **Environment Management**: We will use a dedicated virtual environment with `uv` / `pip` to install dependencies and execute tests.

---

## Proposed Changes

```
AI-Infra-Summit-Hackathon/
├── LICENSE                          # MIT License
├── README.md                        # Master documentation & Quickstart
├── requirements.txt                 # Dependencies
├── pyproject.toml                   # Project metadata
├── sim/
│   ├── __init__.py
│   ├── sim_env.py                   # PyBullet inspection station, camera & bins
│   ├── arm_model.py                 # 6-DoF SO-101 / SO-ARM100 URDF generator & loader
│   └── pcb_generator.py             # Procedural PCB board & defect synthesizer
├── inference/
│   ├── __init__.py
│   ├── detector.py                  # OpenVINO defect detector & 2D-to-3D backprojector
│   ├── model_builder.py             # ONNX/OpenVINO model generator for out-of-the-box execution
│   └── benchmark.py                 # Latency & throughput benchmarking script
├── planner/
│   ├── __init__.py
│   ├── kinematics.py                # Analytical/numerical IK & joint limits
│   └── vla_planner.py               # Grasp affordance & multi-waypoint trajectory generator
├── voice/
│   ├── __init__.py
│   ├── voice_agent.py               # Speechmatics streaming client & voice intent handler
│   └── audit_logger.py              # Immutable SQLite & JSON QA audit log
├── dashboard/
│   ├── __init__.py
│   └── app.py                       # Polished Streamlit telemetry & interactive control center
├── tests/
│   ├── __init__.py
│   └── test_pipeline.py             # Pytest test suite (PyBullet, OpenVINO, IK, Voice)
└── docs/
    ├── SUBMISSION_METADATA.md       # Titles, short/long descriptions, tags, business impact
    ├── SLIDES_OUTLINE.md            # 6-slide presentation deck outline
    └── VIDEO_SCRIPT.md              # 3-minute timed video demo script
```

---

## Detailed Component Plan

### 1. Environment & Dependencies (`requirements.txt`, `pyproject.toml`, `LICENSE`)
- Core packages: `pybullet`, `openvino`, `speechmatics-python`, `opencv-python`, `streamlit`, `numpy`, `scipy`, `pydantic`, `pytest`, `torch`, `torchvision` (optional/lightweight), `pillow`.
- MIT License file for open-source compliance.

### 2. Simulation Environment (`sim/`)
- `sim_env.py`:
  - Headless & GUI support via PyBullet (`p.DIRECT` or `p.GUI`).
  - Inspection table, staging conveyor, Bin A (Scrap / Rework - Red/Amber) and Bin B (Assembly Pass - Green/Cyan).
  - Overhead synthetic RGB-D camera (`computeViewMatrixAt`, `computeProjectionMatrixFOV`, `getCameraImage`).
  - Depth buffer linearization and 3D point cloud / coordinate conversion.
- `arm_model.py`:
  - Procedural URDF generator/loader for the 6-DoF SO-101 / SO-ARM100 arm with parallel jaw gripper.
  - Joint limits, link dynamics, visual and collision geometries.
- `pcb_generator.py`:
  - Generates synthetic PCB textures and geometry with procedural traces, IC chips, capacitors, solder pads.
  - Injects realistic defects:
    1. *Solder Bridge* (short circuit across pins)
    2. *Component Misalignment* (rotated/offset SMT part)
    3. *Surface Scratch / Contamination* (deep fissure or flux trace)
    4. *Nominal / Pristine* (zero defects)

### 3. Edge Defect Detection via OpenVINO (`inference/`)
- `model_builder.py`:
  - Synthesizes a compact MobileNet-style / ResNet-style defect classification and detection ONNX network with metadata.
  - Exports to OpenVINO Intermediate Representation (IR: `.xml` + `.bin`).
- `detector.py`:
  - Loads IR or ONNX model using `openvino.runtime.Core()`.
  - Configures CPU/GPU/AUTO execution target with OpenVINO performance hints (`LATENCY` / `THROUGHPUT`).
  - Runs defect inference, computes bounding boxes, confidence score, defect classification.
  - Backprojects 2D bounding box centroids $(u, v)$ and depth $Z$ to real 3D Cartesian coordinates $(X, Y, Z)$ on the inspection bed using camera intrinsic and extrinsic matrices.

### 4. VLA Reasoning & Kinematics Planner (`planner/`)
- `kinematics.py`:
  - 6-DoF inverse kinematics with PyBullet `calculateInverseKinematics` using damped least squares and joint limit clamping.
  - End-effector position & orientation quaternion math.
- `vla_planner.py`:
  - Grasp affordance calculator: computes safe grasp zones on PCB borders, avoiding keep-out zones near IC components and detected defects.
  - Trajectory state machine:
    - `HOME` (neutral ready position)
    - `HOVER` (pre-grasp 80mm above target)
    - `APPROACH` (move down to grasp height)
    - `GRASP` (close parallel gripper fingers with force control)
    - `LIFT` (retract vertically with grasped PCB)
    - `TRAVERSE` (smooth interpolated waypoint arc to target bin)
    - `PLACE` (open gripper to release into Bin A or Bin B)
    - `RETURN` (reset to Home position)

### 5. Speechmatics Voice-Driven QA Control (`voice/`)
- `voice_agent.py`:
  - Speechmatics streaming SDK integration with support for live API tokens or a mock audio simulator with realistic industrial ambient noise.
  - Intent extraction parser handling commands:
    - `"override reject, pass unit"` -> changes routing from Bin A to Bin B
    - `"override pass, scrap unit"` -> changes routing from Bin B to Bin A
    - `"flag recurring bridge defect"` -> triggers alert & logs high-priority engineering ticket
    - `"emergency stop"` / `"pause line"` -> halts robot motion
    - `"resume line"` -> resumes autonomous cycle
- `audit_logger.py`:
  - Immutable SQLite and JSON event logs: stores unit timestamp, defect metadata, 3D coordinates, voice transcript, operator ID, confidence, and resulting arm trajectory.

### 6. Live Web Application & Dashboard (`dashboard/app.py`)
- Built with Streamlit:
  - **Live Camera & Perception**: High-resolution PyBullet camera render with overlaid OpenVINO bounding boxes, class tag, confidence, and 3D coordinates.
  - **Real-time Telemetry Cards**: OpenVINO inference latency (ms), IK solve time (ms), total cycle time (s), pass/fail yield rate.
  - **Voice Command Station**: Live Speechmatics transcript waterfall, recognized intent badge, and quick-action trigger buttons (e.g., "Simulate Speech: Override Reject", "Simulate Speech: Flag Defect").
  - **Robotic Arm Status**: Joint angles, end-effector pose, active trajectory state, bin statistics.

### 7. Verification & Testing (`tests/test_pipeline.py`)
- Automated Pytest suite testing:
  - PyBullet headless initialization, camera image tensor generation, and physics stability.
  - OpenVINO model compilation, inference execution, and <30ms latency constraint.
  - Camera 2D-to-3D projection accuracy against ground-truth coordinate markers.
  - Inverse kinematics convergence within positional tolerance (<5mm).
  - Speechmatics intent parsing for standard and malformed voice commands.
  - End-to-end full sorting cycle execution (spawn -> inspect -> plan -> move -> drop).

### 8. Submission Collateral (`docs/`)
- `SUBMISSION_METADATA.md`: Hackathon submission form fields ready for lablab.ai copy-paste.
- `SLIDES_OUTLINE.md`: Professional 6-slide presentation deck outline.
- `VIDEO_SCRIPT.md`: Timed 3-minute video presentation script with audio narration and on-screen visual directions.

---

## Verification Plan

### Automated Tests
- Setup virtual environment with `uv venv .venv` and install all required packages.
- Run `pytest tests/test_pipeline.py -v` to ensure all unit and integration tests pass.
- Run `python inference/benchmark.py` to verify OpenVINO latency metrics on CPU.

### Manual Verification
- Launch the Streamlit dashboard (`streamlit run dashboard/app.py --server.headless true`) and verify the UI rendering, camera feed, and simulated voice interaction.
- Verify that simulation produces visually verified inspection images saved to `assets/`.
