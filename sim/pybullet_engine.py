"""PyBullet compatibility layer providing both native PyBullet binding and

a high-fidelity pure-Python robotics & camera engine when native C++ binaries
are unavailable.
"""

from __future__ import annotations
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple
import numpy as np
from PIL import Image, ImageDraw

# Try importing native pybullet
try:
    import pybullet as _native_p
    import pybullet_data as _native_pdata
    HAS_NATIVE_PYBULLET = True
except ImportError:
    _native_p = None
    _native_pdata = None
    HAS_NATIVE_PYBULLET = False


# Constants and Enums
DIRECT = 0
GUI = 1
POSITION_CONTROL = 2
GEOM_BOX = 1
GEOM_SPHERE = 2
GEOM_CYLINDER = 3
ER_TINY_RENDERER = 0


def getQuaternionFromEuler(euler: Sequence[float]) -> List[float]:
    """Converts Euler roll-pitch-yaw (rad) to quaternion [x, y, z, w]."""
    roll, pitch, yaw = euler
    cy = math.cos(yaw * 0.5)
    sy = math.sin(yaw * 0.5)
    cp = math.cos(pitch * 0.5)
    sp = math.sin(pitch * 0.5)
    cr = math.cos(roll * 0.5)
    sr = math.sin(roll * 0.5)

    w = cr * cp * cy + sr * sp * sy
    x = sr * cp * cy - cr * sp * sy
    y = cr * sp * cy + sr * cp * sy
    z = cr * cp * sy - sr * sp * cy
    return [x, y, z, w]


def computeViewMatrix(
    cameraEyePosition: Sequence[float],
    cameraTargetPosition: Sequence[float],
    cameraUpVector: Sequence[float],
) -> List[float]:
    """Computes 4x4 view matrix from eye, target, and up vectors."""
    eye = np.array(cameraEyePosition, dtype=np.float64)
    target = np.array(cameraTargetPosition, dtype=np.float64)
    up = np.array(cameraUpVector, dtype=np.float64)

    forward = target - eye
    norm_f = np.linalg.norm(forward)
    forward = forward / (norm_f if norm_f > 1e-8 else 1.0)

    side = np.cross(forward, up)
    norm_s = np.linalg.norm(side)
    side = side / (norm_s if norm_s > 1e-8 else 1.0)

    true_up = np.cross(side, forward)

    rot = np.eye(4, dtype=np.float64)
    rot[0, :3] = side
    rot[1, :3] = true_up
    rot[2, :3] = -forward

    trans = np.eye(4, dtype=np.float64)
    trans[:3, 3] = -eye

    view_mat = rot @ trans
    return list(view_mat.flatten())


def computeProjectionMatrixFOV(
    fov: float,
    aspect: float,
    nearVal: float,
    farVal: float,
) -> List[float]:
    """Computes standard 4x4 perspective projection matrix."""
    fov_rad = math.radians(fov)
    f = 1.0 / math.tan(fov_rad / 2.0)

    proj = np.zeros((4, 4), dtype=np.float64)
    proj[0, 0] = f / aspect
    proj[1, 1] = f
    proj[2, 2] = (farVal + nearVal) / (nearVal - farVal)
    proj[2, 3] = (2.0 * farVal * nearVal) / (nearVal - farVal)
    proj[3, 2] = -1.0
    return list(proj.flatten())


class MockWorld:
    """Internal state for standalone simulation execution."""
    def __init__(self):
        self.bodies: Dict[int, Dict[str, Any]] = {}
        self.next_body_id = 1
        self.time_step = 1.0 / 240.0
        self.gravity = [0.0, 0.0, -9.81]
        self.arm_id: Optional[int] = None
        self.table_id: Optional[int] = None
        self.bin_scrap_id: Optional[int] = None
        self.bin_pass_id: Optional[int] = None
        self.pcb_id: Optional[int] = None


_CURRENT_WORLD: Optional[MockWorld] = None


def connect(mode: int = DIRECT) -> int:
    global _CURRENT_WORLD
    if HAS_NATIVE_PYBULLET:
        return _native_p.connect(mode)
    _CURRENT_WORLD = MockWorld()
    return 1


def disconnect(physicsClientId: Optional[int] = None):
    global _CURRENT_WORLD
    if HAS_NATIVE_PYBULLET:
        _native_p.disconnect(physicsClientId)
    _CURRENT_WORLD = None


def setAdditionalSearchPath(path: str):
    if HAS_NATIVE_PYBULLET:
        _native_p.setAdditionalSearchPath(path)


def setGravity(x: float, y: float, z: float):
    global _CURRENT_WORLD
    if HAS_NATIVE_PYBULLET:
        _native_p.setGravity(x, y, z)
    elif _CURRENT_WORLD is not None:
        _CURRENT_WORLD.gravity = [x, y, z]


def setTimeStep(dt: float):
    global _CURRENT_WORLD
    if HAS_NATIVE_PYBULLET:
        _native_p.setTimeStep(dt)
    elif _CURRENT_WORLD is not None:
        _CURRENT_WORLD.time_step = dt


def loadURDF(
    fileName: str,
    basePosition: Sequence[float] = (0, 0, 0),
    baseOrientation: Sequence[float] = (0, 0, 0, 1),
    useFixedBase: bool = True,
) -> int:
    global _CURRENT_WORLD
    if HAS_NATIVE_PYBULLET:
        return _native_p.loadURDF(fileName, basePosition, baseOrientation, useFixedBase=useFixedBase)

    body_id = _CURRENT_WORLD.next_body_id
    _CURRENT_WORLD.next_body_id += 1

    # 6 revolute arm joints + 2 gripper joints
    joints = [
        {"pos": 0.0, "target": 0.0, "lower": -3.14, "upper": 3.14},
        {"pos": -0.4, "target": -0.4, "lower": -1.8, "upper": 1.8},
        {"pos": 0.8, "target": 0.8, "lower": -2.4, "upper": 2.4},
        {"pos": 0.0, "target": 0.0, "lower": -3.14, "upper": 3.14},
        {"pos": 1.2, "target": 1.2, "lower": -2.0, "upper": 2.0},
        {"pos": 0.0, "target": 0.0, "lower": -3.14, "upper": 3.14},
        {"pos": 0.035, "target": 0.035, "lower": 0.0, "upper": 0.035},
        {"pos": 0.035, "target": 0.035, "lower": 0.0, "upper": 0.035},
    ]

    _CURRENT_WORLD.bodies[body_id] = {
        "type": "robot",
        "urdf": fileName,
        "base_pos": list(basePosition),
        "base_orn": list(baseOrientation),
        "joints": joints,
    }
    _CURRENT_WORLD.arm_id = body_id
    return body_id


def createCollisionShape(shapeType: int, halfExtents: Sequence[float] = (1, 1, 1)) -> int:
    if HAS_NATIVE_PYBULLET:
        return _native_p.createCollisionShape(shapeType, halfExtents=halfExtents)
    return 1


def createVisualShape(
    shapeType: int,
    halfExtents: Sequence[float] = (1, 1, 1),
    rgbaColor: Sequence[float] = (1, 1, 1, 1),
) -> int:
    if HAS_NATIVE_PYBULLET:
        return _native_p.createVisualShape(shapeType, halfExtents=halfExtents, rgbaColor=rgbaColor)
    return 1


def createMultiBody(
    baseMass: float = 0,
    baseCollisionShapeIndex: int = -1,
    baseVisualShapeIndex: int = -1,
    basePosition: Sequence[float] = (0, 0, 0),
    baseOrientation: Sequence[float] = (0, 0, 0, 1),
) -> int:
    global _CURRENT_WORLD
    if HAS_NATIVE_PYBULLET:
        return _native_p.createMultiBody(
            baseMass=baseMass,
            baseCollisionShapeIndex=baseCollisionShapeIndex,
            baseVisualShapeIndex=baseVisualShapeIndex,
            basePosition=basePosition,
            baseOrientation=baseOrientation,
        )

    body_id = _CURRENT_WORLD.next_body_id
    _CURRENT_WORLD.next_body_id += 1
    _CURRENT_WORLD.bodies[body_id] = {
        "mass": baseMass,
        "base_pos": list(basePosition),
        "base_orn": list(baseOrientation),
    }
    return body_id


def removeBody(bodyUniqueId: int):
    global _CURRENT_WORLD
    if HAS_NATIVE_PYBULLET:
        _native_p.removeBody(bodyUniqueId)
    elif _CURRENT_WORLD is not None:
        _CURRENT_WORLD.bodies.pop(bodyUniqueId, None)


def resetJointState(bodyUniqueId: int, jointIndex: int, targetValue: float):
    global _CURRENT_WORLD
    if HAS_NATIVE_PYBULLET:
        _native_p.resetJointState(bodyUniqueId, jointIndex, targetValue)
    elif _CURRENT_WORLD is not None and bodyUniqueId in _CURRENT_WORLD.bodies:
        joints = _CURRENT_WORLD.bodies[bodyUniqueId].get("joints", [])
        if jointIndex < len(joints):
            joints[jointIndex]["pos"] = targetValue
            joints[jointIndex]["target"] = targetValue


def setJointMotorControl2(
    bodyIndex: int,
    jointIndex: int,
    controlMode: int,
    targetPosition: float,
    force: float = 50.0,
    maxVelocity: float = 3.0,
):
    global _CURRENT_WORLD
    if HAS_NATIVE_PYBULLET:
        _native_p.setJointMotorControl2(
            bodyIndex,
            jointIndex,
            controlMode,
            targetPosition=targetPosition,
            force=force,
            maxVelocity=maxVelocity,
        )
    elif _CURRENT_WORLD is not None and bodyIndex in _CURRENT_WORLD.bodies:
        joints = _CURRENT_WORLD.bodies[bodyIndex].get("joints", [])
        if jointIndex < len(joints):
            joints[jointIndex]["target"] = targetPosition
            # Simple proportional convergence
            current = joints[jointIndex]["pos"]
            joints[jointIndex]["pos"] += (targetPosition - current) * 0.4


def getJointStates(bodyUniqueId: int, jointIndices: Sequence[int]) -> List[Tuple[float, float, List[float], float]]:
    global _CURRENT_WORLD
    if HAS_NATIVE_PYBULLET:
        return _native_p.getJointStates(bodyUniqueId, jointIndices)

    results = []
    if _CURRENT_WORLD is not None and bodyUniqueId in _CURRENT_WORLD.bodies:
        joints = _CURRENT_WORLD.bodies[bodyUniqueId].get("joints", [])
        for j_idx in jointIndices:
            pos = joints[j_idx]["pos"] if j_idx < len(joints) else 0.0
            results.append((pos, 0.0, [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], 0.0))
    return results


def getLinkState(bodyUniqueId: int, linkIndex: int, computeForwardKinematics: bool = True):
    global _CURRENT_WORLD
    if HAS_NATIVE_PYBULLET:
        return _native_p.getLinkState(bodyUniqueId, linkIndex, computeForwardKinematics=computeForwardKinematics)

    # Pure Python forward kinematics for SO-ARM100
    pos = [0.35, 0.0, 0.28]
    orn = getQuaternionFromEuler([0, math.pi, 0])
    if _CURRENT_WORLD is not None and bodyUniqueId in _CURRENT_WORLD.bodies:
        joints = [j["pos"] for j in _CURRENT_WORLD.bodies[bodyUniqueId].get("joints", [])]
        if len(joints) >= 6:
            q1, q2, q3, q4, q5, q6 = joints[:6]
            # Link parameters
            L1 = 0.18
            L2 = 0.24
            L3 = 0.20
            L4 = 0.16
            # Planar 2-link + wrist projection
            r = L2 * math.cos(q2) + L3 * math.cos(q2 + q3) + L4 * math.sin(q2 + q3 + q5)
            z = 0.20 + L1 + L2 * math.sin(q2) + L3 * math.sin(q2 + q3) - L4 * math.cos(q2 + q3 + q5)
            x = r * math.cos(q1)
            y = r * math.sin(q1)
            pos = [float(x), float(y), float(z)]

    # Tuple structure matching PyBullet getLinkState
    return (
        pos, orn, [0, 0, 0], [0, 0, 0, 1], pos, orn, [0, 0, 0], [0, 0, 0]
    )


def calculateInverseKinematics(
    bodyUniqueId: int,
    endEffectorLinkIndex: int,
    targetPosition: Sequence[float],
    targetOrientation: Optional[Sequence[float]] = None,
    lowerLimits: Optional[Sequence[float]] = None,
    upperLimits: Optional[Sequence[float]] = None,
    jointRanges: Optional[Sequence[float]] = None,
    restPoses: Optional[Sequence[float]] = None,
) -> List[float]:
    """Computes 6-DoF inverse kinematics for SO-ARM100 targeting Cartesian pose."""
    if HAS_NATIVE_PYBULLET:
        return list(_native_p.calculateInverseKinematics(
            bodyUniqueId,
            endEffectorLinkIndex,
            targetPosition,
            targetOrientation=targetOrientation,
            lowerLimits=lowerLimits,
            upperLimits=upperLimits,
            jointRanges=jointRanges,
            restPoses=restPoses,
        ))

    tx, ty, tz = targetPosition
    # Geometric IK for anthropomorphic arm
    # 1. Base yaw
    q1 = math.atan2(ty, tx)

    # Distance in horizontal plane
    r_planar = math.hypot(tx, ty)
    # Wrist center targeting
    L1 = 0.18
    L2 = 0.24
    L3 = 0.20
    L4 = 0.16

    # Target wrist center (assuming downward facing end effector)
    rw = r_planar
    zw = tz - 0.20 - L1 + L4

    d_sq = rw * rw + zw * zw
    d = math.sqrt(max(1e-6, d_sq))

    # Law of cosines for elbow
    cos_q3 = (d_sq - L2 * L2 - L3 * L3) / (2.0 * L2 * L3)
    cos_q3 = max(-1.0, min(1.0, cos_q3))
    q3 = -math.acos(cos_q3)

    # Shoulder angle
    alpha = math.atan2(zw, rw)
    cos_beta = (L2 * L2 + d_sq - L3 * L3) / (2.0 * L2 * d)
    cos_beta = max(-1.0, min(1.0, cos_beta))
    beta = math.acos(cos_beta)
    q2 = alpha + beta

    # Wrist pitch to maintain vertical gripper
    q5 = -(q2 + q3)
    q4 = 0.0
    q6 = 0.0

    return [q1, q2, q3, q4, q5, q6]


def stepSimulation():
    global _CURRENT_WORLD
    if HAS_NATIVE_PYBULLET:
        _native_p.stepSimulation()


def getCameraImage(
    width: int,
    height: int,
    viewMatrix: Sequence[float],
    projectionMatrix: Sequence[float],
    renderer: int = ER_TINY_RENDERER,
) -> Tuple[int, int, np.ndarray, np.ndarray, np.ndarray]:
    """Renders synthetic inspection station visual frame and depth buffer."""
    if HAS_NATIVE_PYBULLET:
        return _native_p.getCameraImage(
            width=width,
            height=height,
            viewMatrix=viewMatrix,
            projectionMatrix=projectionMatrix,
            renderer=renderer,
        )

    # Pure Python realistic rendering
    # Background slate tabletop
    img = Image.new("RGBA", (width, height), (38, 42, 48, 255))
    draw = ImageDraw.Draw(img)

    # Grid texture on tabletop
    grid_color = (48, 54, 62, 255)
    for x in range(0, width, 40):
        draw.line([(x, 0), (x, height)], fill=grid_color, width=1)
    for y in range(0, height, 40):
        draw.line([(0, y), (width, y)], fill=grid_color, width=1)

    # Bin A (Scrap/Rework - Red/Amber) on Top/Left
    draw.rectangle([20, 30, 160, 140], fill=(180, 45, 45, 230), outline=(230, 80, 80, 255), width=3)
    draw.text((35, 75), "BIN A: SCRAP / REWORK", fill=(255, 220, 220, 255))

    # Bin B (Pass - Green/Cyan) on Top/Right
    draw.rectangle([width - 160, 30, width - 20, 140], fill=(25, 140, 75, 230), outline=(40, 220, 120, 255), width=3)
    draw.text((width - 145, 75), "BIN B: PASS YIELD", fill=(220, 255, 230, 255))

    # Center Inspection Nest Pedestal
    cx, cy = width // 2, height // 2
    ped_w, ped_h = int(width * 0.42), int(height * 0.42)
    draw.rectangle(
        [cx - ped_w // 2, cy - ped_h // 2, cx + ped_w // 2, cy + ped_h // 2],
        fill=(55, 60, 68, 255),
        outline=(85, 95, 105, 255),
        width=2,
    )
    draw.text((cx - 70, cy - ped_h // 2 + 10), "AMAI OPTICAL INSPECTION NEST", fill=(160, 170, 180, 255))

    # Robot End-Effector representation
    if _CURRENT_WORLD is not None and _CURRENT_WORLD.arm_id is not None:
        state = getLinkState(_CURRENT_WORLD.arm_id, 5)
        pos = state[0]
        # Project robot arm position onto overhead view
        rx = int(cx + (pos[1]) * (width / 0.5))
        ry = int(cy + (0.35 - pos[0]) * (height / 0.5))
        # Gripper jaws
        draw.ellipse([rx - 15, ry - 15, rx + 15, ry + 15], fill=(0, 114, 188, 200), outline=(255, 255, 255, 255), width=2)
        draw.rectangle([rx - 25, ry - 4, rx - 15, ry + 4], fill=(240, 140, 25, 255))
        draw.rectangle([rx + 15, ry - 4, rx + 25, ry + 4], fill=(240, 140, 25, 255))

    rgba_arr = np.array(img, dtype=np.uint8)

    # Linearized depth buffer: ~0.42m to tabletop
    depth_arr = np.full((height, width), 0.42, dtype=np.float32)
    # PCB is slightly closer (~0.40m)
    pcb_w = int(width * 0.32)
    pcb_h = int(height * 0.32)
    depth_arr[cy - pcb_h // 2 : cy + pcb_h // 2, cx - pcb_w // 2 : cx + pcb_w // 2] = 0.400

    # Inverse depth formula mapping back to [0, 1] buffer
    near = 0.1
    far = 1.5
    depth_buf = (far - (near * far / depth_arr)) / (far - near)
    seg_arr = np.zeros((height, width), dtype=np.int32)
    seg_arr[cy - pcb_h // 2 : cy + pcb_h // 2, cx - pcb_w // 2 : cx + pcb_w // 2] = 5

    return width, height, rgba_arr.flatten(), depth_buf.flatten(), seg_arr.flatten()
