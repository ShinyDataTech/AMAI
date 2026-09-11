"""PyBullet physical simulation environment for micro-assembly inspection and robotic sorting."""

from __future__ import annotations
import math
import os
import time
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

from sim import pybullet_engine as p


from sim.arm_model import ArmConfig, get_arm_urdf_path
from sim.pcb_generator import DefectType, PCBGenerator, PCBMetadata


class SimulationStation:
    """Manages PyBullet physics world, SO-ARM100 robot arm, inspection table,

    sorting bins (Bin A: Scrap/Rework, Bin B: Pass), and calibrated overhead RGB-D camera.
    """

    def __init__(
        self,
        gui: bool = False,
        camera_width: int = 640,
        camera_height: int = 480,
    ):
        self.gui = gui
        self.cam_w = camera_width
        self.cam_h = camera_height
        self.physics_client = None
        self.robot_id = None
        self.table_id = None
        self.bin_scrap_id = None
        self.bin_pass_id = None
        self.pcb_id = None
        self.current_pcb_meta: Optional[PCBMetadata] = None
        self.pcb_generator = PCBGenerator()

        # Camera parameters
        self.cam_fov = 50.0
        self.cam_near = 0.1
        self.cam_far = 1.5
        self.cam_eye = [0.35, 0.0, 0.62]      # 42cm directly above inspection nest
        self.cam_target = [0.35, 0.0, 0.20]   # Inspection nest center
        self.cam_up = [0.0, 1.0, 0.0]

        # Workspace Station Geometries
        self.table_pos = [0.35, 0.0, 0.10]
        self.table_size = [0.25, 0.35, 0.10]   # Half-extents: 50cm x 70cm x 20cm
        self.bin_scrap_pos = [0.20, -0.32, 0.10] # Bin A (Scrap/Rework)
        self.bin_pass_pos = [0.20, 0.32, 0.10]   # Bin B (Pass/Assembly)
        self.pcb_spawn_pos = [0.35, 0.0, 0.202]  # Centered on inspection nest

        self._init_simulation()

    def _init_simulation(self):
        """Initializes PyBullet physics engine, gravity, and ground planes."""
        if p is None:
            raise RuntimeError("pybullet is not installed. Please install requirements.")

        connection_mode = p.GUI if self.gui else p.DIRECT
        self.physics_client = p.connect(connection_mode)
        try:
            import pybullet_data
            p.setAdditionalSearchPath(pybullet_data.getDataPath())
            p.loadURDF("plane.urdf")
        except Exception:
            pass

        # Build Inspection Table & Bins
        self._build_workcell_fixtures()

        # Load 6-DoF Arm
        urdf_path = get_arm_urdf_path()
        self.robot_id = p.loadURDF(
            urdf_path,
            basePosition=[0.0, 0.0, 0.20],
            baseOrientation=p.getQuaternionFromEuler([0, 0, 0]),
            useFixedBase=True,
        )

        self.reset_arm()

    def _build_workcell_fixtures(self):
        """Constructs inspection pedestal and color-coded sorting bins."""
        # Central Inspection Pedestal
        pedestal_col = p.createCollisionShape(p.GEOM_BOX, halfExtents=self.table_size)
        pedestal_vis = p.createVisualShape(
            p.GEOM_BOX,
            halfExtents=self.table_size,
            rgbaColor=[0.18, 0.20, 0.24, 1.0],  # Matte slate
        )
        self.table_id = p.createMultiBody(
            baseMass=0,
            baseCollisionShapeIndex=pedestal_col,
            baseVisualShapeIndex=pedestal_vis,
            basePosition=self.table_pos,
        )

        # Bin A: Scrap / Rework (Red/Amber)
        bin_size = [0.10, 0.12, 0.08]
        bin_a_col = p.createCollisionShape(p.GEOM_BOX, halfExtents=bin_size)
        bin_a_vis = p.createVisualShape(
            p.GEOM_BOX,
            halfExtents=bin_size,
            rgbaColor=[0.85, 0.22, 0.22, 0.85],  # Translucent Warning Red
        )
        self.bin_scrap_id = p.createMultiBody(
            baseMass=0,
            baseCollisionShapeIndex=bin_a_col,
            baseVisualShapeIndex=bin_a_vis,
            basePosition=self.bin_scrap_pos,
        )

        # Bin B: Pass / Certified Assembly (Cyan/Green)
        bin_b_col = p.createCollisionShape(p.GEOM_BOX, halfExtents=bin_size)
        bin_b_vis = p.createVisualShape(
            p.GEOM_BOX,
            halfExtents=bin_size,
            rgbaColor=[0.12, 0.75, 0.45, 0.85],  # Translucent Certified Green
        )
        self.bin_pass_id = p.createMultiBody(
            baseMass=0,
            baseCollisionShapeIndex=bin_b_col,
            baseVisualShapeIndex=bin_b_vis,
            basePosition=self.bin_pass_pos,
        )

    def reset_arm(self):
        """Sets robot joints to neutral home configuration."""
        for joint_idx, angle in zip(ArmConfig.ARM_JOINTS, ArmConfig.HOME_JOINTS):
            p.resetJointState(self.robot_id, joint_idx, angle)
            p.setJointMotorControl2(
                self.robot_id,
                joint_idx,
                p.POSITION_CONTROL,
                targetPosition=angle,
                force=50.0,
            )
        self.set_gripper(ArmConfig.GRIPPER_OPEN)

    def set_gripper(self, width: float):
        """Actuates parallel jaw gripper fingers."""
        half_width = width / 2.0
        for joint_idx in ArmConfig.GRIPPER_JOINTS:
            p.setJointMotorControl2(
                self.robot_id,
                joint_idx,
                p.POSITION_CONTROL,
                targetPosition=half_width,
                force=30.0,
            )

    def set_arm_joints(self, target_angles: List[float]):
        """Sets target position for 6 arm joints."""
        for joint_idx, angle in zip(ArmConfig.ARM_JOINTS, target_angles):
            p.setJointMotorControl2(
                self.robot_id,
                joint_idx,
                p.POSITION_CONTROL,
                targetPosition=angle,
                force=50.0,
                maxVelocity=3.0,
            )

    def get_arm_joint_positions(self) -> List[float]:
        """Returns current joint positions for arm joints."""
        states = p.getJointStates(self.robot_id, ArmConfig.ARM_JOINTS)
        return [s[0] for s in states]

    def get_ee_pose(self) -> Tuple[List[float], List[float]]:
        """Returns (position, orientation_quaternion) of end-effector link."""
        state = p.getLinkState(self.robot_id, ArmConfig.EE_LINK_INDEX, computeForwardKinematics=True)
        pos = list(state[4])  # worldLinkFramePosition
        orn = list(state[5])  # worldLinkFrameOrientation
        return pos, orn

    def spawn_pcb(
        self,
        defect_type: Optional[DefectType] = None,
        seed: Optional[int] = None,
    ) -> PCBMetadata:
        """Removes previous PCB and spawns a new procedural PCB on inspection bed."""
        if self.pcb_id is not None:
            p.removeBody(self.pcb_id)
            self.pcb_id = None

        pcb_meta = self.pcb_generator.generate(defect_type=defect_type, seed=seed)
        self.current_pcb_meta = pcb_meta

        # Half extents of the PCB
        half_x = pcb_meta.board_width_m / 2.0
        half_y = pcb_meta.board_length_m / 2.0
        half_z = pcb_meta.board_thickness_m / 2.0

        pcb_col = p.createCollisionShape(p.GEOM_BOX, halfExtents=[half_x, half_y, half_z])
        # Dark emerald FR4 color
        pcb_vis = p.createVisualShape(
            p.GEOM_BOX,
            halfExtents=[half_x, half_y, half_z],
            rgbaColor=[0.08, 0.35, 0.18, 1.0],
        )

        spawn_z = self.table_pos[2] + self.table_size[2] + half_z
        self.pcb_spawn_pos = [self.table_pos[0], self.table_pos[1], spawn_z]

        self.pcb_id = p.createMultiBody(
            baseMass=0.045,  # 45 grams
            baseCollisionShapeIndex=pcb_col,
            baseVisualShapeIndex=pcb_vis,
            basePosition=self.pcb_spawn_pos,
            baseOrientation=p.getQuaternionFromEuler([0, 0, 0]),
        )

        # Save texture to assets for camera projection
        texture_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "assets",
            "current_pcb.png",
        )
        self.pcb_generator.save_texture(pcb_meta, texture_path)
        try:
            tex_id = p.loadTexture(texture_path)
            p.changeVisualShape(self.pcb_id, -1, textureUniqueId=tex_id)
        except Exception:
            pass

        self.step(20)
        return pcb_meta

    def render_overhead_camera(self) -> Dict[str, np.ndarray]:
        """Renders calibrated overhead RGB-D image of the inspection station."""
        view_matrix = p.computeViewMatrix(
            cameraEyePosition=self.cam_eye,
            cameraTargetPosition=self.cam_target,
            cameraUpVector=self.cam_up,
        )
        aspect = float(self.cam_w) / float(self.cam_h)
        proj_matrix = p.computeProjectionMatrixFOV(
            fov=self.cam_fov,
            aspect=aspect,
            nearVal=self.cam_near,
            farVal=self.cam_far,
        )

        _, _, rgba, depth_buf, seg_mask = p.getCameraImage(
            width=self.cam_w,
            height=self.cam_h,
            viewMatrix=view_matrix,
            projectionMatrix=proj_matrix,
            renderer=p.ER_TINY_RENDERER,
        )

        rgba_arr = np.reshape(rgba, (self.cam_h, self.cam_w, 4)).astype(np.uint8)
        rgb_arr = rgba_arr[:, :, :3]

        depth_buf = np.reshape(depth_buf, (self.cam_h, self.cam_w))
        # Linearize depth buffer to meters
        depth_m = self.cam_far * self.cam_near / (self.cam_far - (self.cam_far - self.cam_near) * depth_buf)

        # If we have a textured PCB in memory, composite the high-res texture onto the PCB region
        # to ensure micro-features are crisp and clean for OpenVINO edge detection
        composite_rgb = self._composite_pcb_texture(rgb_arr)

        return {
            "rgb": composite_rgb,
            "depth": depth_m.astype(np.float32),
            "seg": np.reshape(seg_mask, (self.cam_h, self.cam_w)).astype(np.int32),
            "view_matrix": np.array(view_matrix).reshape(4, 4),
            "proj_matrix": np.array(proj_matrix).reshape(4, 4),
        }

    def _composite_pcb_texture(self, base_rgb: np.ndarray) -> np.ndarray:
        """High-fidelity composition of procedural PCB texture onto camera frame for sub-millimeter vision."""
        if self.current_pcb_meta is None:
            return base_rgb

        out_rgb = base_rgb.copy()
        # PCB is centered in camera view. Calculate pixel bounds:
        cx, cy = self.cam_w // 2, self.cam_h // 2
        # Scale: ~180px x 130px for a 10cm x 7cm PCB at 42cm distance with 50 deg FOV
        tex_w = int(self.cam_w * 0.32)
        tex_h = int(self.cam_h * 0.32)
        x1 = cx - tex_w // 2
        y1 = cy - tex_h // 2
        x2 = x1 + tex_w
        y2 = y1 + tex_h

        pcb_img_resized = self.current_pcb_meta.image.resize((tex_w, tex_h), Image.Resampling.BICUBIC)
        pcb_arr = np.array(pcb_img_resized)

        # Inset blend
        out_rgb[y1:y2, x1:x2] = pcb_arr
        return out_rgb

    def deproject_pixel_to_3d(self, u: float, v: float, depth_m: float) -> Tuple[float, float, float]:
        """Converts image coordinates (u, v) in pixels and depth in meters

        to world 3D Cartesian coordinates (X, Y, Z).
        """
        # Normalized Device Coordinates (NDC) in [-1, 1]
        ndc_x = (2.0 * u / self.cam_w) - 1.0
        ndc_y = 1.0 - (2.0 * v / self.cam_h)

        aspect = float(self.cam_w) / float(self.cam_h)
        fov_rad = math.radians(self.cam_fov)
        tan_half_fov = math.tan(fov_rad / 2.0)

        # Camera frame coordinates
        x_c = ndc_x * depth_m * tan_half_fov * aspect
        y_c = ndc_y * depth_m * tan_half_fov
        z_c = -depth_m

        # Camera eye pose
        # Camera is looking straight down along -Z (world frame coordinates mapped)
        # Eye at [0.35, 0.0, 0.62], up is [0, 1, 0]
        # In this configuration:
        # Cam X -> World X
        # Cam Y -> World Y
        # Cam Z -> -World Z
        world_x = self.cam_eye[0] + x_c
        world_y = self.cam_eye[1] + y_c
        world_z = self.cam_eye[2] + z_c

        return (world_x, world_y, world_z)

    def step(self, steps: int = 1):
        """Steps the physics simulation forward."""
        for _ in range(steps):
            p.stepSimulation()

    def close(self):
        """Cleans up PyBullet physics connection."""
        if self.physics_client is not None:
            p.disconnect(self.physics_client)
            self.physics_client = None
