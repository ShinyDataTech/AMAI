"""Procedural URDF generator and configuration for 6-DoF SO-101 / SO-ARM100 robotic arm."""

from __future__ import annotations
import os
from typing import Dict, List, Tuple

SO_ARM100_URDF = """<?xml version="1.0"?>
<robot name="so_arm100">
  <!-- Base Link -->
  <link name="base_link">
    <visual>
      <origin xyz="0 0 0.04" rpy="0 0 0"/>
      <geometry>
        <cylinder radius="0.08" length="0.08"/>
      </geometry>
      <material name="dark_gray">
        <color rgba="0.2 0.22 0.25 1.0"/>
      </material>
    </visual>
    <collision>
      <origin xyz="0 0 0.04" rpy="0 0 0"/>
      <geometry>
        <cylinder radius="0.08" length="0.08"/>
      </geometry>
    </collision>
    <inertial>
      <mass value="1.5"/>
      <inertia ixx="0.005" ixy="0" ixz="0" iyy="0.005" iyz="0" izz="0.008"/>
    </inertial>
  </link>

  <!-- Joint 1: Base Yaw -->
  <joint name="joint_1" type="revolute">
    <parent link="base_link"/>
    <child link="link_1"/>
    <origin xyz="0 0 0.08" rpy="0 0 0"/>
    <axis xyz="0 0 1"/>
    <limit lower="-3.14159" upper="3.14159" effort="20.0" velocity="2.5"/>
    <dynamics damping="0.5" friction="0.1"/>
  </joint>

  <!-- Link 1: Shoulder Base -->
  <link name="link_1">
    <visual>
      <origin xyz="0 0 0.05" rpy="0 0 0"/>
      <geometry>
        <box size="0.07 0.07 0.10"/>
      </geometry>
      <material name="intel_blue">
        <color rgba="0.0 0.44 0.73 1.0"/>
      </material>
    </visual>
    <collision>
      <origin xyz="0 0 0.05" rpy="0 0 0"/>
      <geometry>
        <box size="0.07 0.07 0.10"/>
      </geometry>
    </collision>
    <inertial>
      <mass value="0.8"/>
      <inertia ixx="0.002" ixy="0" ixz="0" iyy="0.002" iyz="0" izz="0.002"/>
    </inertial>
  </link>

  <!-- Joint 2: Shoulder Pitch -->
  <joint name="joint_2" type="revolute">
    <parent link="link_1"/>
    <child link="link_2"/>
    <origin xyz="0 0 0.10" rpy="0 0 0"/>
    <axis xyz="0 1 0"/>
    <limit lower="-1.8" upper="1.8" effort="30.0" velocity="2.0"/>
    <dynamics damping="0.5" friction="0.1"/>
  </joint>

  <!-- Link 2: Upper Arm -->
  <link name="link_2">
    <visual>
      <origin xyz="0 0 0.12" rpy="0 0 0"/>
      <geometry>
        <box size="0.05 0.05 0.24"/>
      </geometry>
      <material name="silver">
        <color rgba="0.75 0.77 0.80 1.0"/>
      </material>
    </visual>
    <collision>
      <origin xyz="0 0 0.12" rpy="0 0 0"/>
      <geometry>
        <box size="0.05 0.05 0.24"/>
      </geometry>
    </collision>
    <inertial>
      <mass value="1.0"/>
      <inertia ixx="0.004" ixy="0" ixz="0" iyy="0.004" iyz="0" izz="0.001"/>
    </inertial>
  </link>

  <!-- Joint 3: Elbow Pitch -->
  <joint name="joint_3" type="revolute">
    <parent link="link_2"/>
    <child link="link_3"/>
    <origin xyz="0 0 0.24" rpy="0 0 0"/>
    <axis xyz="0 1 0"/>
    <limit lower="-2.4" upper="2.4" effort="20.0" velocity="2.5"/>
    <dynamics damping="0.5" friction="0.1"/>
  </joint>

  <!-- Link 3: Forearm -->
  <link name="link_3">
    <visual>
      <origin xyz="0 0 0.10" rpy="0 0 0"/>
      <geometry>
        <box size="0.04 0.04 0.20"/>
      </geometry>
      <material name="intel_blue"/>
    </visual>
    <collision>
      <origin xyz="0 0 0.10" rpy="0 0 0"/>
      <geometry>
        <box size="0.04 0.04 0.20"/>
      </geometry>
    </collision>
    <inertial>
      <mass value="0.7"/>
      <inertia ixx="0.003" ixy="0" ixz="0" iyy="0.003" iyz="0" izz="0.001"/>
    </inertial>
  </link>

  <!-- Joint 4: Wrist Roll -->
  <joint name="joint_4" type="revolute">
    <parent link="link_3"/>
    <child link="link_4"/>
    <origin xyz="0 0 0.20" rpy="0 0 0"/>
    <axis xyz="0 0 1"/>
    <limit lower="-3.14159" upper="3.14159" effort="10.0" velocity="3.0"/>
    <dynamics damping="0.2" friction="0.05"/>
  </joint>

  <!-- Link 4: Wrist 1 -->
  <link name="link_4">
    <visual>
      <origin xyz="0 0 0.03" rpy="0 0 0"/>
      <geometry>
        <cylinder radius="0.03" length="0.06"/>
      </geometry>
      <material name="dark_gray"/>
    </visual>
    <collision>
      <origin xyz="0 0 0.03" rpy="0 0 0"/>
      <geometry>
        <cylinder radius="0.03" length="0.06"/>
      </geometry>
    </collision>
    <inertial>
      <mass value="0.3"/>
      <inertia ixx="0.0005" ixy="0" ixz="0" iyy="0.0005" iyz="0" izz="0.0005"/>
    </inertial>
  </link>

  <!-- Joint 5: Wrist Pitch -->
  <joint name="joint_5" type="revolute">
    <parent link="link_4"/>
    <child link="link_5"/>
    <origin xyz="0 0 0.06" rpy="0 0 0"/>
    <axis xyz="0 1 0"/>
    <limit lower="-2.0" upper="2.0" effort="10.0" velocity="3.0"/>
    <dynamics damping="0.2" friction="0.05"/>
  </joint>

  <!-- Link 5: Wrist 2 -->
  <link name="link_5">
    <visual>
      <origin xyz="0 0 0.03" rpy="0 0 0"/>
      <geometry>
        <box size="0.04 0.04 0.06"/>
      </geometry>
      <material name="silver"/>
    </visual>
    <collision>
      <origin xyz="0 0 0.03" rpy="0 0 0"/>
      <geometry>
        <box size="0.04 0.04 0.06"/>
      </geometry>
    </collision>
    <inertial>
      <mass value="0.2"/>
      <inertia ixx="0.0003" ixy="0" ixz="0" iyy="0.0003" iyz="0" izz="0.0003"/>
    </inertial>
  </link>

  <!-- Joint 6: Wrist Yaw / Tool Flange -->
  <joint name="joint_6" type="revolute">
    <parent link="link_5"/>
    <child link="ee_link"/>
    <origin xyz="0 0 0.06" rpy="0 0 0"/>
    <axis xyz="0 0 1"/>
    <limit lower="-3.14159" upper="3.14159" effort="8.0" velocity="3.5"/>
    <dynamics damping="0.1" friction="0.02"/>
  </joint>

  <!-- End-Effector Base -->
  <link name="ee_link">
    <visual>
      <origin xyz="0 0 0.02" rpy="0 0 0"/>
      <geometry>
        <box size="0.06 0.04 0.04"/>
      </geometry>
      <material name="dark_gray"/>
    </visual>
    <collision>
      <origin xyz="0 0 0.02" rpy="0 0 0"/>
      <geometry>
        <box size="0.06 0.04 0.04"/>
      </geometry>
    </collision>
    <inertial>
      <mass value="0.2"/>
      <inertia ixx="0.0002" ixy="0" ixz="0" iyy="0.0002" iyz="0" izz="0.0002"/>
    </inertial>
  </link>

  <!-- Gripper Left Finger Joint -->
  <joint name="gripper_left_joint" type="prismatic">
    <parent link="ee_link"/>
    <child link="gripper_left_finger"/>
    <origin xyz="0.02 0 0.04" rpy="0 0 0"/>
    <axis xyz="1 0 0"/>
    <limit lower="0.0" upper="0.035" effort="25.0" velocity="0.2"/>
    <dynamics damping="1.0" friction="0.5"/>
  </joint>

  <!-- Gripper Left Finger Link -->
  <link name="gripper_left_finger">
    <visual>
      <origin xyz="0 0 0.025" rpy="0 0 0"/>
      <geometry>
        <box size="0.008 0.02 0.05"/>
      </geometry>
      <material name="intel_orange">
        <color rgba="0.95 0.55 0.1 1.0"/>
      </material>
    </visual>
    <collision>
      <origin xyz="0 0 0.025" rpy="0 0 0"/>
      <geometry>
        <box size="0.008 0.02 0.05"/>
      </geometry>
    </collision>
    <inertial>
      <mass value="0.05"/>
      <inertia ixx="0.00001" ixy="0" ixz="0" iyy="0.00001" iyz="0" izz="0.00001"/>
    </inertial>
  </link>

  <!-- Gripper Right Finger Joint -->
  <joint name="gripper_right_joint" type="prismatic">
    <parent link="ee_link"/>
    <child link="gripper_right_finger"/>
    <origin xyz="-0.02 0 0.04" rpy="0 0 0"/>
    <axis xyz="-1 0 0"/>
    <limit lower="0.0" upper="0.035" effort="25.0" velocity="0.2"/>
    <dynamics damping="1.0" friction="0.5"/>
  </joint>

  <!-- Gripper Right Finger Link -->
  <link name="gripper_right_finger">
    <visual>
      <origin xyz="0 0 0.025" rpy="0 0 0"/>
      <geometry>
        <box size="0.008 0.02 0.05"/>
      </geometry>
      <material name="intel_orange"/>
    </visual>
    <collision>
      <origin xyz="0 0 0.025" rpy="0 0 0"/>
      <geometry>
        <box size="0.008 0.02 0.05"/>
      </geometry>
    </collision>
    <inertial>
      <mass value="0.05"/>
      <inertia ixx="0.00001" ixy="0" ixz="0" iyy="0.00001" iyz="0" izz="0.00001"/>
    </inertial>
  </link>
</robot>
"""

class ArmConfig:
    ARM_JOINTS = [0, 1, 2, 3, 4, 5]
    GRIPPER_JOINTS = [6, 7]
    EE_LINK_INDEX = 5  # ee_link index in kinematic chain
    
    # Neutral home configuration
    HOME_JOINTS = [0.0, -0.4, 0.8, 0.0, 1.2, 0.0]
    
    # Joint limits (min, max) in radians
    JOINT_LIMITS: List[Tuple[float, float]] = [
        (-3.14159, 3.14159),  # Joint 1: Base Yaw
        (-1.8, 1.8),          # Joint 2: Shoulder Pitch
        (-2.4, 2.4),          # Joint 3: Elbow Pitch
        (-3.14159, 3.14159),  # Joint 4: Wrist Roll
        (-2.0, 2.0),          # Joint 5: Wrist Pitch
        (-3.14159, 3.14159),  # Joint 6: Wrist Yaw
    ]

    GRIPPER_OPEN = 0.035
    GRIPPER_CLOSED = 0.008


def get_arm_urdf_path() -> str:
    """Writes the procedural URDF to assets/so_arm100.urdf and returns absolute path."""
    assets_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
    os.makedirs(assets_dir, exist_ok=True)
    urdf_path = os.path.join(assets_dir, "so_arm100.urdf")
    with open(urdf_path, "w", encoding="utf-8") as f:
        f.write(SO_ARM100_URDF.strip())
    return urdf_path
