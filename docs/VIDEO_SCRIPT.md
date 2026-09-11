# 3-Minute Video Pitch & Demonstration Script: AMAI

**Target Duration:** 3 minutes (180 seconds)  
**Tone:** Confident, technical, high-energy industrial robotics demonstration.

---

### [00:00 - 00:30] Introduction & The Problem
**Visual:** 
- Opening slide with AMAI logo, Intel OpenVINO and Speechmatics badges.
- Transition to a high-resolution view of a synthetic PCB with a microscopic solder bridge across IC pins.

**Narration:**
> *"In electronics manufacturing, precision is measured in micrometers. A single microscopic solder bridge or a component misaligned by two degrees can destroy an automotive ECU or medical device. But today, inspection and robotics live in separate worlds: optical inspection cameras flag errors, but human operators still have to manually sort, transport, and log defective boards.
>
> Today, we present **AMAI: The Adaptive Micro-Assembly Inspector**—a Physical AI workcell that fuses **Intel OpenVINO™ edge vision**, **6-DoF robotic manipulation**, and **Speechmatics streaming voice intelligence** into a self-governing assembly station."*

---

### [00:30 - 01:15] Physical AI Simulation & Intel OpenVINO Perception
**Visual:**
- Screen recording of the Streamlit dashboard.
- Clicking **"Random Unit"** and showing the overhead calibrated RGB-D camera view.
- Zooming in on the detected defect bounding box and the telemetry card showing: `Latency: 0.24 ms`.
- Switching view mode to **"Linearized Depth Field"** to highlight sub-millimeter 3D depth measurement.

**Narration:**
> *"Here in our Streamlit command center, you're looking at our physical simulation environment. An overhead calibrated RGB-D camera observes the inspection nest.
>
> When a board arrives, our **Intel OpenVINO™ 2026** edge detector processes the frame in just **0.24 milliseconds**—that's over 2,300 frames per second on standard Intel hardware, well within our 30-millisecond industrial cycle budget!
>
> OpenVINO classifies the defect—in this case, a critical solder bridge shorting pins on the central MCU. It estimates the 2D bounding box, and our camera deprojection engine instantly calculates the exact 3D Cartesian coordinates of the fault."*

---

### [01:15 - 02:00] VLA Grasp Reasoning & 6-DoF Robotic Sorting
**Visual:**
- Animation of the 6-DoF SO-ARM100 manipulator moving through the multi-waypoint trajectory.
- Close-up of the parallel jaw gripper grasping the safe outer rail of the PCB, avoiding sensitive silicon and defects.
- Arm traversing and depositing the defective board into **Bin A (Red / Scrap-Rework)**.
- Triggering a **"Pristine Pass"** board and watching the arm smoothly route it to **Bin B (Green / Certified Pass)**.

**Narration:**
> *"Next comes our VLA motion planner. The robot can't just grab the board anywhere—it must avoid sensitive components and the defect zone itself. Our grasp affordance planner identifies the safe outer border rails.
>
> Using analytical inverse kinematics, the 6-DoF SO-ARM100 arm executes a deterministic 9-waypoint trajectory: Hover, Approach, Secure Grasp, Lift, Traverse, and Deposit. Defective boards are automatically routed to Bin A for rework, while nominal units are sorted into Bin B for final assembly."*

---

### [02:00 - 02:35] Speechmatics Streaming Voice Supervision
**Visual:**
- Moving to the Speechmatics Voice Station on the right panel.
- Clicking **"Override Reject, Pass Unit"**.
- The Speechmatics transcription HUD lights up showing: `"Override reject, pass unit to assembly" | Intent: OVERRIDE_PASS | Confidence: 98%`.
- The arm immediately responds, diverting the unit to Bin B.
- Clicking **"Emergency Stop"** and showing the safety interlock trigger.

**Narration:**
> *"Factory technicians wear ESD gloves and hold inspection tools; they cannot be tied to a keyboard or mouse. That's where **Speechmatics streaming voice intelligence** transforms operations.
>
> With hands-free natural speech, an engineer can supervise the cell. When an operator says: 'Override reject, pass unit to assembly', Speechmatics transcribes the command in real-time, extracts the formal industrial intent, and re-routes the unit to Bin B.
>
> Technicians can say 'Emergency Stop' to instantly lock all six joints, or 'Flag recurring defect' to notify quality engineering—all hands-free."*

---

### [02:35 - 03:00] Immutable Audit Trail & Conclusion
**Visual:**
- Scrolling to the bottom SQLite audit trail table.
- Clicking **"Export Audit JSON"** showing full traceability data.
- Running `pytest tests/test_pipeline.py` in terminal showing `7 passed in 0.53s`.
- Closing title slide with GitHub URL.

**Narration:**
> *"Every single physical action, confidence score, 3D coordinate, and operator voice transcript is permanently logged to an immutable SQLite audit trail for full ISO-9001 compliance.
>
> AMAI is 100% open-source, fully reproducible with zero external hardware keys, and passes all automated tests in half a second.
>
> By combining **Intel OpenVINO's** sub-millisecond edge vision with **Speechmatics'** natural voice oversight, AMAI delivers the future of autonomous, human-supervised Physical AI. Thank you!"*
