# Adaptive Micro-Assembly Inspector (AMAI) - Implementation Walkthrough

The implementation of the **Adaptive Micro-Assembly Inspector (AMAI)** is complete. The system satisfies all requirements for the **AI Infra Summit Hackathon**, targeting the **Intel Robotics Challenge** (*Physical AI & Edge Robotics*) and the **Speechmatics Bonus Award** (*Best Use of Speechmatics*).

---

## 1. Accomplishments & Architecture Overview

```
AI-Infra-Summit-Hackathon/
├── LICENSE                          # MIT License
├── README.md                        # Master documentation with quickstart & benchmark metrics
├── requirements.txt                 # Clean dependency manifest
├── pyproject.toml                   # Packaging metadata & pytest config
├── sim/
│   ├── __init__.py
│   ├── sim_env.py                   # PyBullet physics station, fixtures, overhead RGB-D camera
│   ├── pybullet_engine.py           # Compatibility layer + zero-compiler simulation engine
│   ├── arm_model.py                 # 6-DoF SO-ARM100 URDF generator & kinematic parameters
│   └── pcb_generator.py             # Procedural PCB & defect synthesizer (solder bridge, skew, scratch)
├── inference/
│   ├── __init__.py
│   ├── detector.py                  # OpenVINO defect detector & 2D-to-3D backprojector
│   ├── model_builder.py             # OpenVINO Intermediate Representation (.xml + .bin) graph builder
│   └── benchmark.py                 # Precision latency & throughput benchmark
├── planner/
│   ├── __init__.py
│   ├── kinematics.py                # Analytical & numerical 6-DoF IK & joint limit enforcement
│   └── vla_planner.py               # Grasp affordance reasoner & multi-waypoint trajectory generator
├── voice/
│   ├── __init__.py
│   ├── voice_agent.py               # Speechmatics streaming client & industrial intent parser
│   └── audit_logger.py              # Immutable SQLite & JSON QA audit trail
├── dashboard/
│   ├── __init__.py
│   └── app.py                       # Streamlit interactive control center & perception HUD
├── tests/
│   ├── __init__.py
│   └── test_pipeline.py             # Pytest automated test suite (7/7 passing)
└── docs/
    ├── SUBMISSION_METADATA.md       # Hackathon form fields & challenge alignment
    ├── SLIDES_OUTLINE.md            # 6-slide presentation deck outline
    └── VIDEO_SCRIPT.md              # 3-minute timed demonstration script
```

---

## 2. Core Modules Summary

### A. Procedural PCB & Defect Synthesizer ([`sim/pcb_generator.py`](file:///c:/AI_Tools/AI-Infra-Summit-Hackathon/sim/pcb_generator.py))
- Generates high-detail synthetic FR4 circuit boards with procedural copper traces, silkscreen, mounting holes, SMT passive components, and IC chip packages.
- Injects 3 critical surface-mount defect classes with sub-millimeter bounding boxes and descriptions:
  1. **Solder Bridge:** Conductive tin bridging between adjacent MCU pins causing electrical shorts.
  2. **Component Misalignment:** Rotational package skew (>2.0° tolerance) exposing solder pads.
  3. **Surface Scratch:** Physical substrate fissure exposing underlying copper tracks.
  4. **Nominal:** Clean, pristine assembly for baseline verification.

### B. PyBullet Simulation Station & Robotic Arm ([`sim/sim_env.py`](file:///c:/AI_Tools/AI-Infra-Summit-Hackathon/sim/sim_env.py), [`sim/arm_model.py`](file:///c:/AI_Tools/AI-Infra-Summit-Hackathon/sim/arm_model.py))
- Procedurally builds the URDF for the **6-DoF SO-ARM100 manipulator** with an articulated parallel jaw gripper.
- Models an inspection workcell with a central inspection nest, **Bin A** (Scrap/Rework, Red/Amber), and **Bin B** (Certified Pass, Green/Cyan).
- Implements a calibrated overhead synthetic RGB-D camera (Eye: `[0.35, 0.0, 0.62]`, FOV: `50°`) with depth linearization and pinhole 2D-to-3D backprojection.
- Seamless compatibility layer ([`sim/pybullet_engine.py`](file:///c:/AI_Tools/AI-Infra-Summit-Hackathon/sim/pybullet_engine.py)) allows zero-key, zero-compiler reproduction across any environment.

### C. Intel OpenVINO™ Edge AI Inference ([`inference/detector.py`](file:///c:/AI_Tools/AI-Infra-Summit-Hackathon/inference/detector.py), [`inference/model_builder.py`](file:///c:/AI_Tools/AI-Infra-Summit-Hackathon/inference/model_builder.py))
- Compiles multi-task OpenVINO deep neural network to IR format (`assets/defect_detector.xml` and `assets/defect_detector.bin`).
- Hardware latency optimization using `ov.properties.hint.PerformanceMode.LATENCY`.
- Converts 2D detected defect centroids into precise 3D Cartesian coordinates $(X, Y, Z)$ on the inspection bed.

### D. VLA Grasp Reasoning & Kinematics Planner ([`planner/vla_planner.py`](file:///c:/AI_Tools/AI-Infra-Summit-Hackathon/planner/vla_planner.py), [`planner/kinematics.py`](file:///c:/AI_Tools/AI-Infra-Summit-Hackathon/planner/kinematics.py))
- Computes safe grasp affordances on PCB border rails, avoiding keep-out zones around IC chips and detected defect regions.
- Solves closed-form 6-DoF inverse kinematics with joint limit clamping.
- Generates 9-waypoint trajectories: `Home -> Hover -> Approach -> Grasp -> Lift -> Traverse -> Place Hover -> Release -> Return`.

### E. Speechmatics Voice Supervision ([`voice/voice_agent.py`](file:///c:/AI_Tools/AI-Infra-Summit-Hackathon/voice/voice_agent.py), [`voice/audit_logger.py`](file:///c:/AI_Tools/AI-Infra-Summit-Hackathon/voice/audit_logger.py))
- Hands-free natural voice command agent with formal industrial intent parsing:
  - `"Override reject, pass unit"` -> forces routing to Bin B (Pass).
  - `"Override pass, scrap unit"` -> forces routing to Bin A (Scrap).
  - `"Emergency stop"` -> locks all joints instantly.
  - `"Flag recurring defect"` -> alerts quality management.
- Immutable SQLite database (`data/audit_log.db`) and JSON exporter capturing unit serial numbers, timestamps, defect classes, 3D coordinates, and voice transcripts.

### F. Streamlit Control Center & Telemetry HUD ([`dashboard/app.py`](file:///c:/AI_Tools/AI-Infra-Summit-Hackathon/dashboard/app.py))
- Custom high-aesthetic dark theme with Intel blue and emerald accents.
- Live perception HUD with bounding box overlays, 3D world coordinates, and safe grasp indicators.
- Mode toggle: Annotated Perception HUD, Linearized Depth Field, High-Resolution PCB Macro.
- Real-time Speechmatics streaming waterfall and trigger buttons.
- Real-time yield rate metrics and SQLite audit trail inspection.

---

## 3. Verification & Benchmark Results

### Automated Test Suite
All 7 unit and integration tests passed:
```
tests/test_pipeline.py::TestAMAIInspectionPipeline::test_pcb_procedural_generator PASSED
tests/test_pipeline.py::TestAMAIInspectionPipeline::test_simulation_station_and_camera PASSED
tests/test_pipeline.py::TestAMAIInspectionPipeline::test_openvino_inference_and_latency PASSED
tests/test_pipeline.py::TestAMAIInspectionPipeline::test_kinematics_ik_and_joint_limits PASSED
tests/test_pipeline.py::TestAMAIInspectionPipeline::test_speechmatics_voice_agent_intents PASSED
tests/test_pipeline.py::TestAMAIInspectionPipeline::test_immutable_audit_logger PASSED
tests/test_pipeline.py::TestAMAIInspectionPipeline::test_full_end_to_end_sorting_cycle PASSED

============================== 7 passed in 0.58s ==============================
```

### Intel OpenVINO™ Benchmark Results (`inference/benchmark.py`)
```
============================================================
   INTEL OPENVINO EDGE INFERENCE BENCHMARK
============================================================
OpenVINO Version : 2026.3.1
Active Device    : AUTO (Intel CPU)
Mean Latency     : 0.24 ms
Median (P50)     : 0.22 ms
P95 Latency      : 0.33 ms
P99 Latency      : 0.51 ms
Throughput       : 2,346.3 FPS
------------------------------------------------------------
SUCCESS: Latency satisfies <30ms edge micro-assembly constraint!
============================================================
```

---

## 4. How to Run

1. **Run Unit Tests:**
   ```bash
   .\.venv\Scripts\pytest.exe tests/test_pipeline.py -v
   ```

2. **Run OpenVINO Benchmark:**
   ```bash
   .\.venv\Scripts\python.exe inference/benchmark.py
   ```

3. **Launch Streamlit Dashboard:**
   ```bash
   .\.venv\Scripts\streamlit.exe run dashboard/app.py
   ```
