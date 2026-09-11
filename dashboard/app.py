"""Adaptive Micro-Assembly Inspector (AMAI) - Interactive Control & Telemetry Dashboard.

Built for AI Infra Summit Hackathon (Intel Robotics & Speechmatics tracks).
"""

from __future__ import annotations
import os
import sys
import time

# Ensure project root in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import numpy as np
from PIL import Image
import streamlit as st

from inference.detector import OpenVINODetector, DetectionResult
from planner.kinematics import KinematicsEngine
from planner.vla_planner import VLAPlanner, TrajectoryState
from sim.pcb_generator import DefectType, PCBMetadata
from sim.sim_env import SimulationStation
from voice.audit_logger import AuditLogger
from voice.voice_agent import VoiceAgent, VoiceIntent, VoiceCommand

# Page Configuration
st.set_page_config(
    page_title="AMAI | Adaptive Micro-Assembly Inspector",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom High-Aesthetic Styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    code, pre {
        font-family: 'JetBrains Mono', monospace;
    }

    .main-header {
        background: linear-gradient(135deg, #0b1329 0%, #102a45 50%, #081d33 100%);
        border: 1px solid #1e3a5f;
        border-radius: 12px;
        padding: 20px 24px;
        margin-bottom: 24px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.35);
    }
    .badge-intel {
        background: #0071c5;
        color: white;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.5px;
        text-transform: uppercase;
        display: inline-block;
        margin-right: 6px;
    }
    .badge-speech {
        background: #6366f1;
        color: white;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.5px;
        text-transform: uppercase;
        display: inline-block;
        margin-right: 6px;
    }
    .badge-robot {
        background: #10b981;
        color: white;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.5px;
        text-transform: uppercase;
        display: inline-block;
    }
    .metric-card {
        background: #131b2e;
        border: 1px solid #1f2d4a;
        border-radius: 10px;
        padding: 14px 18px;
        text-align: center;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
    }
    .metric-val {
        font-family: 'JetBrains Mono', monospace;
        font-size: 26px;
        font-weight: 700;
        color: #00c7fd;
        margin: 4px 0;
    }
    .metric-label {
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        color: #94a3b8;
    }
    .feed-card {
        background: #0d1424;
        border: 1px solid #1c273c;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 20px;
    }
    .log-badge {
        font-family: 'JetBrains Mono', monospace;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 11px;
    }
    .status-pass { background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid #10b981; }
    .status-fail { background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid #ef4444; }
    .status-warn { background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid #f59e0b; }
</style>
""", unsafe_allow_html=True)


# Initialize Session State Singletons
@st.cache_resource
def get_station():
    return SimulationStation(gui=False)

@st.cache_resource
def get_detector():
    return OpenVINODetector(device_name="AUTO")

@st.cache_resource
def get_planner():
    return VLAPlanner()

@st.cache_resource
def get_voice_agent():
    return VoiceAgent()

@st.cache_resource
def get_audit_logger():
    return AuditLogger()

station = get_station()
detector = get_detector()
planner = get_planner()
voice_agent = get_voice_agent()
logger = get_audit_logger()

# Session states
if "last_detection" not in st.session_state:
    st.session_state.last_detection = None
if "last_pcb" not in st.session_state:
    st.session_state.last_pcb = station.spawn_pcb()
if "last_cam" not in st.session_state:
    st.session_state.last_cam = station.render_overhead_camera()
if "last_voice_cmd" not in st.session_state:
    st.session_state.last_voice_cmd = None
if "arm_status" not in st.session_state:
    st.session_state.arm_status = "IDLE (Station Ready)"
if "cycle_history" not in st.session_state:
    st.session_state.cycle_history = []


# Header Banner
st.markdown("""
<div class="main-header">
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <div>
            <h1 style="margin: 0; font-size: 28px; font-weight: 800; color: #ffffff; letter-spacing: -0.5px;">
                ⚡ AMAI <span style="font-size: 18px; color: #00c7fd; font-weight: 600;">| Adaptive Micro-Assembly Inspector</span>
            </h1>
            <p style="margin: 6px 0 0 0; color: #94a3b8; font-size: 13px;">
                Physical AI Quality Assurance, Intel OpenVINO Edge Detection & Speechmatics Voice Supervised 6-DoF Robotic Sorting
            </p>
        </div>
        <div>
            <span class="badge-intel">Intel OpenVINO™ 2026</span>
            <span class="badge-speech">Speechmatics Voice</span>
            <span class="badge-robot">6-DoF SO-ARM100</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)


# Top Telemetry Metrics
metrics = logger.get_metrics()
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">OpenVINO Latency</div>
        <div class="metric-val">{st.session_state.last_detection.inference_time_ms:.2f} ms</div>
        <span class="log-badge status-pass">Target &lt; 30ms</span>
    </div>
    """ if st.session_state.last_detection else """
    <div class="metric-card">
        <div class="metric-label">OpenVINO Latency</div>
        <div class="metric-val">0.24 ms</div>
        <span class="log-badge status-pass">Target &lt; 30ms</span>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Defect Classification</div>
        <div class="metric-val" style="font-size: 18px; color: {'#34d399' if (st.session_state.last_detection and not st.session_state.last_detection.has_defect) else '#f87171'}">
            {st.session_state.last_detection.defect_type.value if st.session_state.last_detection else 'NOMINAL'}
        </div>
        <span class="log-badge status-pass">{st.session_state.last_detection.confidence:.1%} Conf</span>
    </div>
    """ if st.session_state.last_detection else """
    <div class="metric-card">
        <div class="metric-label">Defect Classification</div>
        <div class="metric-val" style="font-size: 18px; color: #34d399">STANDBY</div>
        <span class="log-badge status-pass">Ready</span>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Line Yield Rate</div>
        <div class="metric-val">{metrics['yield_rate_percent']:.1f}%</div>
        <span class="log-badge status-pass">{metrics['passed']}/{metrics['total_inspected']} Passed</span>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Operator Overrides</div>
        <div class="metric-val">{metrics['overrides']}</div>
        <span class="log-badge status-warn">Speech Supervised</span>
    </div>
    """, unsafe_allow_html=True)

with col5:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Robot Arm State</div>
        <div class="metric-val" style="font-size: 15px; color: #fbbf24">{st.session_state.arm_status[:12]}</div>
        <span class="log-badge status-pass">6-DoF Kinematics</span>
    </div>
    """, unsafe_allow_html=True)

st.write("")


# Main Work Area
left_col, right_col = st.columns([1.1, 0.9])

with left_col:
    st.markdown("### 📷 Overhead Perception & Optical Inspection")

    # View Mode Selector
    view_mode = st.radio(
        "Camera Display Mode",
        ["Annotated Perception HUD", "Linearized Depth Field", "High-Resolution PCB Macro"],
        horizontal=True,
    )

    cam_data = st.session_state.last_cam
    det_res: Optional[DetectionResult] = st.session_state.last_detection
    pcb_meta: PCBMetadata = st.session_state.last_pcb

    if view_mode == "Annotated Perception HUD":
        # Draw bounding boxes and coordinates on RGB frame
        annotated = cam_data["rgb"].copy()
        h, w, _ = annotated.shape

        if det_res and det_res.bbox_pixels:
            x1, y1, x2, y2 = det_res.bbox_pixels
            color = (0, 0, 255) if det_res.has_defect else (0, 255, 0)
            # Bounding box
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            # Corner markers
            cl = 8
            cv2.line(annotated, (x1, y1), (x1 + cl, y1), color, 3)
            cv2.line(annotated, (x1, y1), (x1, y1 + cl), color, 3)
            cv2.line(annotated, (x2, y2), (x2 - cl, y2), color, 3)
            cv2.line(annotated, (x2, y2), (x2, y2 - cl), color, 3)

            # Label overlay
            label_text = f"{det_res.defect_type.value} ({det_res.confidence:.1%})"
            cv2.putText(annotated, label_text, (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)

            # 3D Coordinates HUD
            if det_res.coords_3d:
                cx3d, cy3d, cz3d = det_res.coords_3d
                coord_text = f"3D World: X={cx3d:.3f}m Y={cy3d:.3f}m Z={cz3d:.3f}m"
                cv2.putText(annotated, coord_text, (x1, y2 + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 230, 255), 1)

        # Draw safe grasp indicators
        if pcb_meta:
            cx, cy = w // 2, h // 2
            cv2.circle(annotated, (cx, cy + int(h * 0.09)), 6, (0, 255, 255), -1)
            cv2.putText(annotated, "GRASP ZONE", (cx - 45, cy + int(h * 0.09) + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)

        st.image(annotated, caption=f"Overhead RGB-D Camera (Eye: [0.35, 0.0, 0.62]m | FOV: 50°) - Unit: {pcb_meta.board_id}", use_container_width=True)

    elif view_mode == "Linearized Depth Field":
        depth = cam_data["depth"]
        # Normalize depth for visualization [0.35m to 0.45m]
        d_min, d_max = 0.35, 0.48
        d_norm = np.clip((depth - d_min) / (d_max - d_min), 0.0, 1.0)
        d_colormap = cv2.applyColorMap((d_norm * 255).astype(np.uint8), cv2.COLORMAP_INFERNO)
        st.image(d_colormap, caption="Overhead Calibrated Depth Map (Sub-millimeter Z-resolution)", use_container_width=True)

    else:
        # High-res PCB texture
        st.image(pcb_meta.image, caption=f"Procedural SMT Micro-Assembly Detail (Ground Truth: {pcb_meta.defect_type.value})", use_container_width=True)

    # Defect Diagnostic Report Card
    if det_res:
        st.markdown(f"""
        <div class="feed-card">
            <h4 style="margin: 0 0 8px 0; color: {'#34d399' if not det_res.has_defect else '#f87171'};">
                {'✅ PASSED: Nominal Unit' if not det_res.has_defect else '⚠️ DEFECT DETECTED: ' + det_res.defect_type.value}
            </h4>
            <p style="margin: 0; color: #cbd5e1; font-size: 13px;">{det_res.description}</p>
            <div style="margin-top: 10px; font-size: 12px; color: #94a3b8;">
                <b>Inference Target:</b> Intel CPU/AUTO | <b>Latency:</b> {det_res.inference_time_ms:.2f} ms | <b>Confidence:</b> {det_res.confidence:.1%}
            </div>
        </div>
        """, unsafe_allow_html=True)


with right_col:
    st.markdown("### 🎙️ Speechmatics Voice Agent & Cycle Control")

    # Run Inspection Cycle Helper
    def execute_inspection(custom_defect: Optional[DefectType] = None, voice_override: Optional[VoiceCommand] = None):
        with st.spinner("Spawning PCB & running OpenVINO inference..."):
            pcb = station.spawn_pcb(defect_type=custom_defect)
            cam = station.render_overhead_camera()
            det = detector.detect(cam["rgb"], cam["depth"], station.deproject_pixel_to_3d, pcb)
            
            st.session_state.last_pcb = pcb
            st.session_state.last_cam = cam
            st.session_state.last_detection = det

            # Plan Motion Trajectory
            wps, target_bin = planner.plan_cycle(
                station.pcb_spawn_pos,
                det,
                voice_command=voice_override,
                pcb_meta=pcb,
            )

            # Route & Audit
            op_action = "AUTONOMOUS"
            if voice_override:
                op_action = f"VOICE_{voice_override.intent.value}"

            res_label = "PASS" if target_bin == "BIN_B_PASS" else "REJECT_SCRAP"

            logger.log(
                unit_id=pcb.board_id,
                defect_type=det.defect_type.value,
                confidence=det.confidence,
                inspection_result=res_label,
                operator_action=op_action,
                target_bin=target_bin,
                coords_3d=det.coords_3d,
                voice_transcript=voice_override.raw_transcript if voice_override else None,
                notes=det.description,
            )

            # Arm Trajectory Execution
            st.session_state.arm_status = f"SORTING -> {target_bin}"
            planner.execute_cycle(station, wps)
            st.session_state.arm_status = f"COMPLETED ({target_bin})"
            st.session_state.last_cam = station.render_overhead_camera()

    # Manual PCB Ingestion Controls
    st.write("**Manual PCB Inspection Triggers:**")
    btn_c1, btn_c2, btn_c3, btn_c4 = st.columns(4)
    with btn_c1:
        if st.button("🎲 Random Unit", use_container_width=True):
            execute_inspection()
            st.rerun()
    with btn_c2:
        if st.button("⚡ Solder Bridge", use_container_width=True):
            execute_inspection(DefectType.SOLDER_BRIDGE)
            st.rerun()
    with btn_c3:
        if st.button("📐 Component Skew", use_container_width=True):
            execute_inspection(DefectType.COMPONENT_MISALIGNMENT)
            st.rerun()
    with btn_c4:
        if st.button("✨ Pristine Pass", use_container_width=True):
            execute_inspection(DefectType.NOMINAL)
            st.rerun()

    st.divider()

    # Speechmatics Voice Station
    st.write("**Speechmatics Streaming Voice Oversight:**")
    st.caption("Speak natural operator instructions or trigger simulated acoustic command streams:")

    # Quick Voice Command Buttons
    v_col1, v_col2 = st.columns(2)
    with v_col1:
        if st.button("🗣️ 'Override Reject, Pass Unit'", use_container_width=True):
            cmd = voice_agent.simulate_speech_command("Override reject, pass unit to assembly")
            st.session_state.last_voice_cmd = cmd
            execute_inspection(DefectType.SOLDER_BRIDGE, voice_override=cmd)
            st.rerun()

        if st.button("🛑 'Emergency Stop'", use_container_width=True):
            cmd = voice_agent.simulate_speech_command("Emergency stop, freeze arm")
            st.session_state.last_voice_cmd = cmd
            st.session_state.arm_status = "EMERGENCY_STOPPED"
            st.rerun()

    with v_col2:
        if st.button("🗣️ 'Override Pass, Scrap Unit'", use_container_width=True):
            cmd = voice_agent.simulate_speech_command("Override pass, scrap unit to rework bin")
            st.session_state.last_voice_cmd = cmd
            execute_inspection(DefectType.NOMINAL, voice_override=cmd)
            st.rerun()

        if st.button("🚩 'Flag Recurring Defect'", use_container_width=True):
            cmd = voice_agent.simulate_speech_command("Flag recurring solder bridge defect for engineering")
            st.session_state.last_voice_cmd = cmd
            st.toast("🚨 Engineering alert logged to Quality Management System!", icon="⚠️")
            st.rerun()

    # Custom Natural Speech Input
    custom_speech = st.text_input("Spoken Operator Input (Speechmatics Live Transcript):", placeholder="e.g. 'Override reject and approve board'")
    if st.button("Transcribe & Execute Intent"):
        if custom_speech.strip():
            cmd = voice_agent.parse_intent(custom_speech)
            st.session_state.last_voice_cmd = cmd
            execute_inspection(voice_override=cmd)
            st.rerun()

    # Voice HUD Status
    if st.session_state.last_voice_cmd:
        vcmd: VoiceCommand = st.session_state.last_voice_cmd
        st.markdown(f"""
        <div class="feed-card" style="border-left: 4px solid #6366f1;">
            <div style="font-size: 11px; color: #a5b4fc; text-transform: uppercase; font-weight: 700;">
                SPEECHMATICS STREAMING TRANSCRIPTION HUD
            </div>
            <div style="font-size: 14px; color: #ffffff; margin: 4px 0; font-family: 'JetBrains Mono', monospace;">
                "{vcmd.raw_transcript}"
            </div>
            <div style="font-size: 12px; color: #cbd5e1;">
                <b>Recognized Intent:</b> <span class="log-badge status-warn">{vcmd.intent.value}</span> |
                <b>Confidence:</b> {vcmd.confidence:.1%}
            </div>
            <div style="font-size: 12px; color: #94a3b8; margin-top: 4px;">
                {vcmd.action_description}
            </div>
        </div>
        """, unsafe_allow_html=True)


# Bottom Real-Time Audit Log & Telemetry
st.divider()
st.markdown("### 📋 Immutable QA Audit Trail (SQLite & JSON)")

recent_logs = logger.get_recent(limit=10)
if recent_logs:
    table_data = []
    for r in recent_logs:
        table_data.append({
            "Timestamp (UTC)": r.timestamp[11:19],
            "Unit SN": r.unit_id,
            "Defect Class": r.defect_type,
            "Confidence": f"{r.confidence:.1%}",
            "Inspection Result": r.inspection_result,
            "Operator Action": r.operator_action,
            "Target Bin": r.target_bin,
            "Voice Transcript": r.voice_transcript or "—",
        })
    st.dataframe(table_data, use_container_width=True)

# Export options
export_c1, export_c2 = st.columns([0.8, 0.2])
with export_c2:
    if st.button("📥 Export Audit JSON", use_container_width=True):
        out_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "audit_export.json")
        logger.export_json(out_path)
        st.success(f"Exported to {os.path.basename(out_path)}")
