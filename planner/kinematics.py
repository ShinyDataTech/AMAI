"""Kinematics engine for 6-DoF SO-ARM100 robot manipulator."""

from __future__ import annotations
import math
from typing import List, Optional, Sequence, Tuple
import numpy as np

from sim.arm_model import ArmConfig
from sim import pybullet_engine as p


class KinematicsEngine:
    """Computes analytical & numerical inverse kinematics, forward kinematics,

    and joint limit enforcement for the 6-DoF SO-ARM100 manipulator.
    """

    # Geometric link parameters (meters)
    L_BASE_Z = 0.20 + 0.08  # Mount pedestal + base link
    L1 = 0.10               # Shoulder offset
    L2 = 0.24               # Upper arm length
    L3 = 0.20               # Forearm length
    L4 = 0.16               # Wrist to tool center point (TCP)

    def __init__(self, robot_id: Optional[int] = None):
        self.robot_id = robot_id
        self.joint_limits = ArmConfig.JOINT_LIMITS

    def compute_ik(
        self,
        target_pos: Sequence[float],
        target_orn: Optional[Sequence[float]] = None,
    ) -> List[float]:
        """Calculates joint angles [q1, q2, q3, q4, q5, q6] in radians for target 3D Cartesian position."""
        if target_orn is None:
            # Default orientation: pointing vertically downward onto PCB surface
            target_orn = p.getQuaternionFromEuler([0, math.pi, 0])

        tx, ty, tz = target_pos

        # Analytical geometric solution for 6-DoF anthropomorphic arm with wrist
        # 1. Base yaw (q1)
        q1 = math.atan2(ty, tx)

        # Planar distance from base axis
        r_planar = math.hypot(tx, ty)

        # Target wrist center point (WCP)
        # Assuming end-effector points downward along -Z:
        rw = r_planar
        zw = tz - self.L_BASE_Z - self.L1 + self.L4

        # Distance from shoulder joint to wrist center
        d_sq = rw * rw + zw * zw
        d = math.sqrt(max(1e-6, d_sq))

        # Law of cosines for elbow pitch (q3)
        cos_q3 = (d_sq - self.L2 * self.L2 - self.L3 * self.L3) / (2.0 * self.L2 * self.L3)
        cos_q3 = max(-1.0, min(1.0, cos_q3))
        q3 = -math.acos(cos_q3)

        # Shoulder pitch (q2)
        alpha = math.atan2(zw, rw)
        cos_beta = (self.L2 * self.L2 + d_sq - self.L3 * self.L3) / (2.0 * self.L2 * d)
        cos_beta = max(-1.0, min(1.0, cos_beta))
        beta = math.acos(cos_beta)
        q2 = alpha + beta

        # Wrist pitch (q5) to maintain vertical tool downward
        q5 = -(q2 + q3)

        # Wrist rolls (neutral)
        q4 = 0.0
        q6 = 0.0

        raw_joints = [q1, q2, q3, q4, q5, q6]
        return self.clamp_joints(raw_joints)

    def clamp_joints(self, joint_angles: Sequence[float]) -> List[float]:
        """Clamps joint angles within mechanical physical limits."""
        clamped = []
        for q, (q_min, q_max) in zip(joint_angles, self.joint_limits):
            clamped.append(float(max(q_min, min(q_max, q))))
        return clamped

    def compute_fk(self, joint_angles: Sequence[float]) -> Tuple[List[float], List[float]]:
        """Calculates forward kinematics TCP position and orientation."""
        q1, q2, q3, q4, q5, q6 = joint_angles[:6]

        r = self.L2 * math.cos(q2) + self.L3 * math.cos(q2 + q3) + self.L4 * math.sin(q2 + q3 + q5)
        z = self.L_BASE_Z + self.L1 + self.L2 * math.sin(q2) + self.L3 * math.sin(q2 + q3) - self.L4 * math.cos(q2 + q3 + q5)
        x = r * math.cos(q1)
        y = r * math.sin(q1)

        pos = [float(x), float(y), float(z)]
        orn = p.getQuaternionFromEuler([0, math.pi, 0])
        return pos, orn

    def validate_pose(
        self,
        target_pos: Sequence[float],
        achieved_pos: Sequence[float],
        tolerance_m: float = 0.015,
    ) -> bool:
        """Verifies if achieved end-effector position is within positional tolerance."""
        error = np.linalg.norm(np.array(target_pos) - np.array(achieved_pos))
        return bool(error <= tolerance_m)
