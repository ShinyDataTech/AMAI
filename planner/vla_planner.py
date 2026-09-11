"""VLA Reasoning, Grasp Affordance, and Multi-Waypoint Trajectory Planner."""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import math
import time
from typing import Callable, List, Optional, Tuple

import numpy as np

from inference.detector import DetectionResult
from planner.kinematics import KinematicsEngine
from sim.arm_model import ArmConfig
from sim.pcb_generator import DefectType, PCBMetadata
from sim.sim_env import SimulationStation
from voice.voice_agent import VoiceCommand, VoiceIntent


class TrajectoryState(str, Enum):
    IDLE = "IDLE"
    HOME = "HOME"
    HOVER = "HOVER"
    APPROACH = "APPROACH"
    GRASP = "GRASP"
    LIFT = "LIFT"
    TRAVERSE = "TRAVERSE"
    PLACE = "PLACE"
    RETURN = "RETURN"
    E_STOP = "E_STOP"


@dataclass
class TrajectoryWaypoint:
    name: str
    state: TrajectoryState
    target_pos: List[float]
    target_joints: List[float]
    gripper_width: float
    description: str


class VLAPlanner:
    """Calculates collision-free grasp affordances and executes deterministic

    motion plans for sorting inspected micro-assemblies into Pass vs. Scrap bins.
    """

    def __init__(self, kinematics: Optional[KinematicsEngine] = None):
        self.kinematics = kinematics or KinematicsEngine()
        self.state = TrajectoryState.IDLE

        # Target Bins Cartesian drop locations
        self.bin_scrap_pos = [0.20, -0.32, 0.22]  # Bin A (Scrap / Rework)
        self.bin_pass_pos = [0.20, 0.32, 0.22]    # Bin B (Certified Pass)
        self.home_pos = [0.30, 0.0, 0.35]

    def compute_grasp_pose(
        self,
        pcb_center_pos: List[float],
        pcb_meta: Optional[PCBMetadata] = None,
        detection: Optional[DetectionResult] = None,
    ) -> List[float]:
        """Calculates collision-free grasp coordinate on PCB border away from

        sensitive IC packages and detected defects.
        """
        cx, cy, cz = pcb_center_pos
        grasp_offset_x = 0.0
        grasp_offset_y = 0.045  # Default grasp on outer side rail

        # If defect is on positive Y border, shift grasp to negative Y border
        if detection and detection.coords_3d:
            dx, dy, _ = detection.coords_3d
            if dy > cy:
                grasp_offset_y = -0.045
            else:
                grasp_offset_y = 0.045

        target_grasp = [cx + grasp_offset_x, cy + grasp_offset_y, cz + 0.005]
        return target_grasp

    def plan_cycle(
        self,
        pcb_pos: List[float],
        detection: DetectionResult,
        voice_command: Optional[VoiceCommand] = None,
        pcb_meta: Optional[PCBMetadata] = None,
    ) -> Tuple[List[TrajectoryWaypoint], str]:
        """Generates a complete multi-waypoint sorting trajectory."""
        # 1. Determine target destination bin
        target_bin = "BIN_A_SCRAP" if detection.has_defect else "BIN_B_PASS"
        routing_reason = "Defect Detected: Routing to Scrap/Rework" if detection.has_defect else "Pass Certified: Routing to Assembly"

        # Check for Voice Override
        if voice_command:
            if voice_command.intent == VoiceIntent.EMERGENCY_STOP:
                return [], "EMERGENCY_STOP_TRIGGERED"
            elif voice_command.intent == VoiceIntent.OVERRIDE_PASS:
                target_bin = "BIN_B_PASS"
                routing_reason = "VOICE OVERRIDE: Authorized for Assembly Pass"
            elif voice_command.intent == VoiceIntent.OVERRIDE_SCRAP:
                target_bin = "BIN_A_SCRAP"
                routing_reason = "VOICE OVERRIDE: Diverted to Scrap/Rework"

        dest_pos = self.bin_pass_pos if target_bin == "BIN_B_PASS" else self.bin_scrap_pos

        # 2. Compute grasp position
        grasp_pos = self.compute_grasp_pose(pcb_pos, pcb_meta, detection)
        hover_pos = [grasp_pos[0], grasp_pos[1], grasp_pos[2] + 0.09]  # 90mm above board
        lift_pos = [grasp_pos[0], grasp_pos[1], grasp_pos[2] + 0.12]   # 120mm lift
        traverse_high = [(hover_pos[0] + dest_pos[0]) / 2.0, (hover_pos[1] + dest_pos[1]) / 2.0, 0.32]
        dest_hover = [dest_pos[0], dest_pos[1], dest_pos[2] + 0.08]

        # 3. Solve IK for all waypoints
        q_home = ArmConfig.HOME_JOINTS
        q_hover = self.kinematics.compute_ik(hover_pos)
        q_approach = self.kinematics.compute_ik(grasp_pos)
        q_lift = self.kinematics.compute_ik(lift_pos)
        q_traverse = self.kinematics.compute_ik(traverse_high)
        q_dest_hover = self.kinematics.compute_ik(dest_hover)
        q_dest = self.kinematics.compute_ik(dest_pos)

        waypoints = [
            TrajectoryWaypoint("Home", TrajectoryState.HOME, self.home_pos, q_home, ArmConfig.GRIPPER_OPEN, "Arm in neutral ready position"),
            TrajectoryWaypoint("Hover", TrajectoryState.HOVER, hover_pos, q_hover, ArmConfig.GRIPPER_OPEN, "Hovering above safe PCB grasp zone"),
            TrajectoryWaypoint("Approach", TrajectoryState.APPROACH, grasp_pos, q_approach, ArmConfig.GRIPPER_OPEN, "Descending to contact grasp plane"),
            TrajectoryWaypoint("Grasp", TrajectoryState.GRASP, grasp_pos, q_approach, ArmConfig.GRIPPER_CLOSED, "Actuating parallel gripper to secure PCB"),
            TrajectoryWaypoint("Lift", TrajectoryState.LIFT, lift_pos, q_lift, ArmConfig.GRIPPER_CLOSED, "Vertical clearance retract"),
            TrajectoryWaypoint("Traverse", TrajectoryState.TRAVERSE, traverse_high, q_traverse, ArmConfig.GRIPPER_CLOSED, f"Traversing to {target_bin}"),
            TrajectoryWaypoint("Place Hover", TrajectoryState.PLACE, dest_hover, q_dest_hover, ArmConfig.GRIPPER_CLOSED, f"Aligning above {target_bin}"),
            TrajectoryWaypoint("Release", TrajectoryState.PLACE, dest_pos, q_dest, ArmConfig.GRIPPER_OPEN, f"Opening gripper to deposit unit into {target_bin}"),
            TrajectoryWaypoint("Return", TrajectoryState.RETURN, self.home_pos, q_home, ArmConfig.GRIPPER_OPEN, "Returning arm to home station"),
        ]

        return waypoints, target_bin

    def execute_cycle(
        self,
        station: SimulationStation,
        waypoints: List[TrajectoryWaypoint],
        step_callback: Optional[Callable[[TrajectoryWaypoint, int, int], None]] = None,
    ) -> bool:
        """Executes the generated trajectory on the simulation station."""
        total = len(waypoints)
        for idx, wp in enumerate(waypoints):
            self.state = wp.state
            station.set_arm_joints(wp.target_joints)
            station.set_gripper(wp.gripper_width)
            station.step(15)

            if step_callback:
                step_callback(wp, idx + 1, total)

        self.state = TrajectoryState.IDLE
        return True
