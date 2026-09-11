"""Procedural PCB board and micro-assembly defect synthesizer."""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
import math
import os
import random
from typing import List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


class DefectType(str, Enum):
    NOMINAL = "NOMINAL"
    SOLDER_BRIDGE = "SOLDER_BRIDGE"
    COMPONENT_MISALIGNMENT = "COMPONENT_MISALIGNMENT"
    SURFACE_SCRATCH = "SURFACE_SCRATCH"


@dataclass
class BoundingBox:
    xmin: float
    ymin: float
    xmax: float
    ymax: float

    @property
    def center(self) -> Tuple[float, float]:
        return ((self.xmin + self.xmax) / 2.0, (self.ymin + self.ymax) / 2.0)

    @property
    def width(self) -> float:
        return self.xmax - self.xmin

    @property
    def height(self) -> float:
        return self.ymax - self.ymin


@dataclass
class PCBMetadata:
    board_id: str
    image: Image.Image
    defect_type: DefectType
    has_defect: bool
    defect_bbox: Optional[BoundingBox]
    confidence_ground_truth: float
    defect_description: str
    board_width_m: float = 0.10   # 100mm
    board_length_m: float = 0.07  # 70mm
    board_thickness_m: float = 0.0016  # 1.6mm FR4 standard
    keep_out_zones: List[BoundingBox] = field(default_factory=list)
    safe_grasp_zones: List[BoundingBox] = field(default_factory=list)


class PCBGenerator:
    """Generates synthetic high-detail PCB textures with procedural IC chips,

    solder joints, circuit traces, and injected micro-assembly defects.
    """

    def __init__(self, image_width: int = 512, image_height: int = 384):
        self.width = image_width
        self.height = image_height

    def generate(
        self,
        defect_type: Optional[DefectType] = None,
        seed: Optional[int] = None,
    ) -> PCBMetadata:
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

        if defect_type is None:
            # 35% nominal, 65% defect distributed across classes
            defect_choice = random.random()
            if defect_choice < 0.35:
                defect_type = DefectType.NOMINAL
            elif defect_choice < 0.60:
                defect_type = DefectType.SOLDER_BRIDGE
            elif defect_choice < 0.80:
                defect_type = DefectType.COMPONENT_MISALIGNMENT
            else:
                defect_type = DefectType.SURFACE_SCRATCH

        # Base FR4 Soldermask colors (deep industrial green / dark emerald)
        base_green = (18, 72, 38)
        img = Image.new("RGB", (self.width, self.height), color=base_green)
        draw = ImageDraw.Draw(img)

        # 1. Background substrate noise / weave pattern
        weave = np.random.randint(-4, 5, (self.height, self.width, 3), dtype=np.int16)
        base_arr = np.array(img, dtype=np.int16) + weave
        base_arr = np.clip(base_arr, 0, 255).astype(np.uint8)
        img = Image.fromarray(base_arr)
        draw = ImageDraw.Draw(img)

        # 2. PCB Gold / Copper edge fingers & grounding rail
        rail_color = (195, 155, 60)
        draw.rectangle([4, 4, self.width - 5, 12], fill=rail_color)
        draw.rectangle([4, self.height - 13, self.width - 5, self.height - 5], fill=rail_color)
        draw.rectangle([4, 4, 12, self.height - 5], fill=rail_color)
        draw.rectangle([self.width - 13, 4, self.width - 5, self.height - 5], fill=rail_color)

        # Mounting holes in 4 corners
        hole_color = (25, 25, 25)
        for hx, hy in [(25, 25), (self.width - 25, 25), (25, self.height - 25), (self.width - 25, self.height - 25)]:
            draw.ellipse([hx - 7, hy - 7, hx + 7, hy + 7], fill=hole_color, outline=(210, 175, 80), width=2)

        # 3. Procedural Copper Traces (routed lines)
        trace_color = (26, 95, 52)
        for _ in range(24):
            x1 = random.randint(30, self.width - 30)
            y1 = random.randint(30, self.height - 30)
            x2 = x1 + random.choice([-80, -40, 40, 80])
            y2 = y1 + random.choice([-60, -30, 30, 60])
            x2 = max(20, min(self.width - 20, x2))
            y2 = max(20, min(self.height - 20, y2))
            draw.line([(x1, y1), (x2, y1), (x2, y2)], fill=trace_color, width=random.choice([2, 3]))

        # 4. SMT Components layout
        # Main MCU/QFP package at center
        mcu_cx = self.width // 2
        mcu_cy = self.height // 2
        mcu_w, mcu_h = 90, 90
        keep_outs: List[BoundingBox] = []

        # Secondary IC chips
        ic2_cx = self.width // 4 + 10
        ic2_cy = self.height // 2 - 20
        ic2_w, ic2_h = 50, 70

        ic3_cx = 3 * self.width // 4 - 10
        ic3_cy = self.height // 2 + 30
        ic3_w, ic3_h = 55, 45

        # Normal draw helper for IC chip package
        def draw_ic(cx: int, cy: int, w: int, h: int, angle: float = 0.0, label: str = "INTEL"):
            # Pin pads around perimeter
            pad_color = (200, 205, 210)  # Tin/Silver solder
            pins_per_side = 8
            # Left & Right pins
            for i in range(pins_per_side):
                py = cy - h // 2 + int((i + 0.5) * (h / pins_per_side))
                draw.rectangle([cx - w // 2 - 12, py - 2, cx - w // 2 - 1, py + 2], fill=pad_color)
                draw.rectangle([cx + w // 2 + 1, py - 2, cx + w // 2 + 12, py + 2], fill=pad_color)

            # Top & Bottom pins
            for i in range(pins_per_side):
                px = cx - w // 2 + int((i + 0.5) * (w / pins_per_side))
                draw.rectangle([px - 2, cy - h // 2 - 12, px + 2, cy - h // 2 - 1], fill=pad_color)
                draw.rectangle([px - 2, cy + h // 2 + 1, px + 2, cy + h // 2 + 12], fill=pad_color)

            # Black epoxy IC package body
            body_color = (32, 34, 36)
            draw.rectangle([cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2], fill=body_color, outline=(60, 64, 68), width=2)
            # Pin 1 index dot
            draw.ellipse([cx - w // 2 + 6, cy - h // 2 + 6, cx - w // 2 + 12, cy - h // 2 + 12], fill=(180, 185, 190))
            # Silkscreen text indicator
            draw.text((cx - w // 4, cy - 6), label, fill=(180, 180, 180))

        # Passive SMT Capacitors and Resistors (0805 / 0603)
        passive_pads: List[Tuple[int, int]] = []
        for _ in range(16):
            px = random.randint(50, self.width - 50)
            py = random.randint(40, self.height - 40)
            # avoid center MCU
            if abs(px - mcu_cx) < 80 and abs(py - mcu_cy) < 80:
                continue
            # solder terminals
            draw.rectangle([px - 8, py - 4, px - 3, py + 4], fill=(210, 215, 220))
            draw.rectangle([px + 3, py - 4, px + 8, py + 4], fill=(210, 215, 220))
            # ceramic body
            body_c = random.choice([(140, 100, 60), (35, 35, 35), (90, 80, 70)])
            draw.rectangle([px - 3, py - 3, px + 3, py + 3], fill=body_c)
            passive_pads.append((px, py))

        # Draw default ICs
        draw_ic(ic2_cx, ic2_cy, ic2_w, ic2_h, label="OPV-24")
        draw_ic(ic3_cx, ic3_cy, ic3_w, ic3_h, label="PHY-AI")

        # Keep out zones around sensitive chips
        keep_outs.append(BoundingBox(
            (mcu_cx - mcu_w // 2 - 20) / self.width,
            (mcu_cy - mcu_h // 2 - 20) / self.height,
            (mcu_cx + mcu_w // 2 + 20) / self.width,
            (mcu_cy + mcu_h // 2 + 20) / self.height,
        ))
        keep_outs.append(BoundingBox(
            (ic2_cx - ic2_w // 2 - 15) / self.width,
            (ic2_cy - ic2_h // 2 - 15) / self.height,
            (ic2_cx + ic2_w // 2 + 15) / self.width,
            (ic2_cy + ic2_h // 2 + 15) / self.height,
        ))
        keep_outs.append(BoundingBox(
            (ic3_cx - ic3_w // 2 - 15) / self.width,
            (ic3_cy - ic3_h // 2 - 15) / self.height,
            (ic3_cx + ic3_w // 2 + 15) / self.width,
            (ic3_cy + ic3_h // 2 + 15) / self.height,
        ))

        # Safe grasp zones on left and right PCB borders (clear of components)
        safe_grasps = [
            BoundingBox(0.02, 0.30, 0.08, 0.70),  # West border
            BoundingBox(0.92, 0.30, 0.98, 0.70),  # East border
        ]

        # Injected defect variables
        defect_bbox: Optional[BoundingBox] = None
        has_defect = False
        confidence = 0.98
        defect_desc = "Nominal unit: 0 critical defects detected. Solder integrity 100%."

        if defect_type == DefectType.NOMINAL:
            draw_ic(mcu_cx, mcu_cy, mcu_w, mcu_h, label="INTEL-AI")
            has_defect = False
            confidence = 0.99
            defect_desc = "Nominal PCB: Solder joints aligned, no shorts, surface integrity pristine."

        elif defect_type == DefectType.SOLDER_BRIDGE:
            draw_ic(mcu_cx, mcu_cy, mcu_w, mcu_h, label="INTEL-AI")
            has_defect = True
            confidence = 0.97
            # Inject solder bridge across adjacent pins on right side of MCU
            bx = mcu_cx + mcu_w // 2 + 6
            by = mcu_cy - 12
            # Molten tin blob bridging 3 pins
            blob_color = (230, 235, 240)
            draw.ellipse([bx - 8, by - 12, bx + 8, by + 12], fill=blob_color, outline=(170, 180, 190), width=1)
            draw.ellipse([bx - 6, by - 8, bx + 6, by + 8], fill=(245, 250, 255))
            defect_desc = f"Critical Solder Bridge defect at ({bx}, {by}): shorted pins 14-16 on U1 QFP package."
            defect_bbox = BoundingBox(
                (bx - 14) / self.width,
                (by - 16) / self.height,
                (bx + 14) / self.width,
                (by + 16) / self.height,
            )

        elif defect_type == DefectType.COMPONENT_MISALIGNMENT:
            has_defect = True
            confidence = 0.95
            # Draw misaligned / skewed MCU
            skew_angle_deg = random.choice([-14.0, -11.0, 12.0, 15.0])
            # Draw rotated package on overlay
            mcu_overlay = Image.new("RGBA", (mcu_w + 50, mcu_h + 50), (0, 0, 0, 0))
            mcu_draw = ImageDraw.Draw(mcu_overlay)
            ocx = (mcu_w + 50) // 2
            ocy = (mcu_h + 50) // 2
            # Rotated pins and body
            mcu_draw.rectangle([ocx - mcu_w // 2, ocy - mcu_h // 2, ocx + mcu_w // 2, ocy + mcu_h // 2],
                               fill=(35, 37, 40, 255), outline=(70, 75, 80, 255), width=2)
            mcu_draw.text((ocx - 20, ocy - 6), "INTEL-AI", fill=(200, 200, 200, 255))
            rotated_mcu = mcu_overlay.rotate(skew_angle_deg, resample=Image.BICUBIC)
            img.paste(rotated_mcu, (mcu_cx - rotated_mcu.width // 2, mcu_cy - rotated_mcu.height // 2), rotated_mcu)

            # Underlying empty solder pads showing skew
            for i in range(6):
                py = mcu_cy - mcu_h // 2 + int((i + 0.5) * (mcu_h / 6))
                draw.rectangle([mcu_cx - mcu_w // 2 - 14, py - 2, mcu_cx - mcu_w // 2 - 4, py + 2], fill=(210, 160, 60))

            defect_desc = f"Component Misalignment defect: IC1 skewed by {skew_angle_deg:.1f}° exceeding ±2.0° IPC-A-610 tolerance."
            defect_bbox = BoundingBox(
                (mcu_cx - mcu_w // 2 - 15) / self.width,
                (mcu_cy - mcu_h // 2 - 15) / self.height,
                (mcu_cx + mcu_w // 2 + 15) / self.width,
                (mcu_cy + mcu_h // 2 + 15) / self.height,
            )

        elif defect_type == DefectType.SURFACE_SCRATCH:
            draw_ic(mcu_cx, mcu_cy, mcu_w, mcu_h, label="INTEL-AI")
            has_defect = True
            confidence = 0.94
            # Deep copper scratch across traces
            sx1 = random.randint(mcu_cx + 40, self.width - 80)
            sy1 = random.randint(40, self.height // 2 - 20)
            sx2 = sx1 + random.randint(30, 70)
            sy2 = sy1 + random.randint(35, 75)
            # Jagged scratch
            scratch_pts = [(sx1, sy1)]
            curr_x, curr_y = sx1, sy1
            steps = 6
            for s in range(steps):
                curr_x += (sx2 - sx1) // steps + random.randint(-4, 4)
                curr_y += (sy2 - sy1) // steps + random.randint(-4, 4)
                scratch_pts.append((curr_x, curr_y))

            draw.line(scratch_pts, fill=(230, 160, 60), width=3)  # Exposed shiny copper
            draw.line(scratch_pts, fill=(255, 230, 200), width=1)  # Core fracture

            defect_desc = f"Surface Scratch defect: Soldermask fracture from ({sx1},{sy1}) to ({sx2},{sy2}) exposing copper traces."
            defect_bbox = BoundingBox(
                min(sx1, sx2) / self.width - 0.03,
                min(sy1, sy2) / self.height - 0.03,
                max(sx1, sx2) / self.width + 0.03,
                max(sy1, sy2) / self.height + 0.03,
            )

        board_id = f"PCB-SN{random.randint(100000, 999999)}"

        return PCBMetadata(
            board_id=board_id,
            image=img,
            defect_type=defect_type,
            has_defect=has_defect,
            defect_bbox=defect_bbox,
            confidence_ground_truth=confidence,
            defect_description=defect_desc,
            board_width_m=0.10,
            board_length_m=0.07,
            board_thickness_m=0.0016,
            keep_out_zones=keep_outs,
            safe_grasp_zones=safe_grasps,
        )

    def save_texture(self, pcb: PCBMetadata, filepath: str) -> str:
        """Saves PCB image to disk for PyBullet visual shape texture mapping."""
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        pcb.image.save(filepath, format="PNG")
        return filepath
