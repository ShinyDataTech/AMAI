"""Comprehensive automated test suite for AMAI micro-assembly inspection pipeline."""

import os
import sys
import pytest
import numpy as np

# Ensure project root in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from inference.detector import OpenVINODetector
from planner.kinematics import KinematicsEngine
from planner.vla_planner import VLAPlanner, TrajectoryState
from sim.pcb_generator import DefectType, PCBGenerator
from sim.sim_env import SimulationStation
from voice.audit_logger import AuditLogger
from voice.voice_agent import VoiceAgent, VoiceIntent


class TestAMAIInspectionPipeline:

    def test_pcb_procedural_generator(self):
        gen = PCBGenerator(image_width=256, image_height=192)
        
        # Test all defect variants
        for d_type in [DefectType.NOMINAL, DefectType.SOLDER_BRIDGE, DefectType.COMPONENT_MISALIGNMENT, DefectType.SURFACE_SCRATCH]:
            pcb = gen.generate(defect_type=d_type, seed=42)
            assert pcb.defect_type == d_type
            assert pcb.image.size == (256, 192)
            assert pcb.board_width_m == 0.10
            assert pcb.board_length_m == 0.07

            if d_type == DefectType.NOMINAL:
                assert not pcb.has_defect
            else:
                assert pcb.has_defect
                assert pcb.defect_bbox is not None
                assert 0.0 <= pcb.defect_bbox.xmin < pcb.defect_bbox.xmax <= 1.0
                assert 0.0 <= pcb.defect_bbox.ymin < pcb.defect_bbox.ymax <= 1.0

    def test_simulation_station_and_camera(self):
        station = SimulationStation(gui=False, camera_width=320, camera_height=240)
        try:
            pcb = station.spawn_pcb(defect_type=DefectType.SOLDER_BRIDGE, seed=123)
            assert pcb.has_defect
            assert station.pcb_id is not None

            cam = station.render_overhead_camera()
            assert cam["rgb"].shape == (240, 320, 3)
            assert cam["depth"].shape == (240, 320)
            assert np.min(cam["depth"]) >= 0.1  # Near plane

            # Test 2D to 3D deprojection
            x3d, y3d, z3d = station.deproject_pixel_to_3d(160, 120, 0.40)
            assert 0.30 <= x3d <= 0.40
            assert -0.05 <= y3d <= 0.05
            assert 0.15 <= z3d <= 0.30
        finally:
            station.close()

    def test_openvino_inference_and_latency(self):
        detector = OpenVINODetector(device_name="AUTO")
        dummy_rgb = np.zeros((480, 640, 3), dtype=np.uint8)
        dummy_depth = np.full((480, 640), 0.42, dtype=np.float32)

        res = detector.detect(dummy_rgb, dummy_depth)
        assert res.inference_time_ms is not None
        # Strict latency budget: must be well below 30ms
        assert res.inference_time_ms < 30.0, f"OpenVINO latency {res.inference_time_ms}ms exceeded 30ms budget"
        assert res.defect_type in OpenVINODetector.CLASS_NAMES

    def test_kinematics_ik_and_joint_limits(self):
        kin = KinematicsEngine()
        target_pos = [0.35, 0.0, 0.22]
        joints = kin.compute_ik(target_pos)

        assert len(joints) == 6
        # Verify within joint limits
        for q, (q_min, q_max) in zip(joints, kin.joint_limits):
            assert q_min <= q <= q_max

        # Forward kinematics verification
        fk_pos, _ = kin.compute_fk(joints)
        assert kin.validate_pose(target_pos, fk_pos, tolerance_m=0.03)

    def test_speechmatics_voice_agent_intents(self):
        agent = VoiceAgent()

        # Pass override
        c1 = agent.parse_intent("Operator override, pass this board to assembly")
        assert c1.intent == VoiceIntent.OVERRIDE_PASS
        assert c1.target_bin == "BIN_B_PASS"

        # Scrap override
        c2 = agent.parse_intent("Force scrap, send unit to rework bin")
        assert c2.intent == VoiceIntent.OVERRIDE_SCRAP
        assert c2.target_bin == "BIN_A_SCRAP"

        # Emergency stop
        c3 = agent.parse_intent("Emergency stop, stop line immediately")
        assert c3.intent == VoiceIntent.EMERGENCY_STOP

        # Resume
        c4 = agent.parse_intent("Resume operation and continue line")
        assert c4.intent == VoiceIntent.RESUME

        # Defect flag
        c5 = agent.parse_intent("Flag recurring solder bridge fault")
        assert c5.intent == VoiceIntent.FLAG_DEFECT

        # Unknown / non-command
        c6 = agent.parse_intent("What is the weather in Seattle today?")
        assert c6.intent == VoiceIntent.UNKNOWN

    def test_immutable_audit_logger(self, tmp_path):
        db_file = str(tmp_path / "test_audit.db")
        logger = AuditLogger(db_path=db_file)

        rec = logger.log(
            unit_id="PCB-SN9999",
            defect_type=DefectType.SOLDER_BRIDGE.value,
            confidence=0.98,
            inspection_result="REJECT_SCRAP",
            operator_action="AUTONOMOUS",
            target_bin="BIN_A_SCRAP",
            coords_3d=(0.35, 0.02, 0.21),
            voice_transcript=None,
            notes="Test entry",
        )

        assert rec.event_id is not None
        recent = logger.get_recent(limit=10)
        assert len(recent) == 1
        assert recent[0].unit_id == "PCB-SN9999"

        # Test metrics
        metrics = logger.get_metrics()
        assert metrics["total_inspected"] == 1
        assert metrics["rejected"] == 1
        assert metrics["yield_rate_percent"] == 0.0

        # Test JSON export
        json_file = str(tmp_path / "audit_export.json")
        logger.export_json(json_file)
        assert os.path.exists(json_file)

    def test_full_end_to_end_sorting_cycle(self):
        station = SimulationStation(gui=False)
        try:
            detector = OpenVINODetector()
            planner = VLAPlanner()

            # Test Scrap sorting cycle
            pcb_defect = station.spawn_pcb(defect_type=DefectType.SOLDER_BRIDGE, seed=777)
            cam = station.render_overhead_camera()
            det = detector.detect(cam["rgb"], cam["depth"], station.deproject_pixel_to_3d, pcb_defect)
            assert det.has_defect

            waypoints, target_bin = planner.plan_cycle(station.pcb_spawn_pos, det, None, pcb_defect)
            assert target_bin == "BIN_A_SCRAP"
            assert len(waypoints) >= 7

            success = planner.execute_cycle(station, waypoints)
            assert success

            # Test Pass sorting cycle
            pcb_nominal = station.spawn_pcb(defect_type=DefectType.NOMINAL, seed=888)
            cam_nom = station.render_overhead_camera()
            det_nom = detector.detect(cam_nom["rgb"], cam_nom["depth"], station.deproject_pixel_to_3d, pcb_nominal)
            assert not det_nom.has_defect

            waypoints_pass, target_bin_pass = planner.plan_cycle(station.pcb_spawn_pos, det_nom, None, pcb_nominal)
            assert target_bin_pass == "BIN_B_PASS"
            success_pass = planner.execute_cycle(station, waypoints_pass)
            assert success_pass
        finally:
            station.close()
