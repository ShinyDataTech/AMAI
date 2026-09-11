"""Generates and exports optimized OpenVINO Intermediate Representation (IR)

models for edge micro-assembly defect detection.
"""

from __future__ import annotations
import os
from typing import Tuple

import numpy as np
import openvino as ov
from openvino import opset13 as ops


def build_and_export_ov_model(
    output_xml_path: str,
) -> Tuple[str, str]:
    """Constructs a multi-task OpenVINO deep neural network for micro-defect

    classification and bounding-box localization, and serializes it to IR (.xml + .bin).
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_xml_path)), exist_ok=True)
    bin_path = output_xml_path.replace(".xml", ".bin")

    # 1. Input: [1, 3, 224, 224] Float32 RGB tensor
    input_shape = [1, 3, 224, 224]
    data_input = ops.parameter(input_shape, dtype=np.float32, name="input_tensor")

    # Conv 1: 3 -> 16 channels, kernel 3x3
    w1 = np.random.randn(16, 3, 3, 3).astype(np.float32) * 0.05
    c1 = ops.convolution(
        data_input,
        ops.constant(w1),
        strides=[2, 2],
        pads_begin=[1, 1],
        pads_end=[1, 1],
        dilations=[1, 1],
    )
    r1 = ops.relu(c1)

    # Conv 2: 16 -> 32 channels, kernel 3x3
    w2 = np.random.randn(32, 16, 3, 3).astype(np.float32) * 0.05
    c2 = ops.convolution(
        r1,
        ops.constant(w2),
        strides=[2, 2],
        pads_begin=[1, 1],
        pads_end=[1, 1],
        dilations=[1, 1],
    )
    r2 = ops.relu(c2)

    # Conv 3: 32 -> 64 channels, kernel 3x3
    w3 = np.random.randn(64, 32, 3, 3).astype(np.float32) * 0.05
    c3 = ops.convolution(
        r2,
        ops.constant(w3),
        strides=[2, 2],
        pads_begin=[1, 1],
        pads_end=[1, 1],
        dilations=[1, 1],
    )
    r3 = ops.relu(c3)

    # Global Average Pooling: [1, 64, 28, 28] -> [1, 64, 1, 1]
    gap = ops.reduce_mean(r3, reduction_axes=[2, 3], keep_dims=False)  # [1, 64]

    # Head 1: Defect Classification (4 classes: NOMINAL, SOLDER_BRIDGE, MISALIGNMENT, SCRATCH)
    w_cls = np.random.randn(64, 4).astype(np.float32) * 0.1
    b_cls = np.array([0.5, 0.1, 0.1, 0.1], dtype=np.float32)  # [4]
    logits = ops.add(ops.matmul(gap, ops.constant(w_cls), transpose_a=False, transpose_b=False), ops.constant(b_cls))
    probs = ops.softmax(logits, axis=1)
    res_cls = ops.result(probs, name="class_probabilities")

    # Head 2: Bounding Box Regression [xmin, ymin, xmax, ymax]
    w_box = np.random.randn(64, 4).astype(np.float32) * 0.05
    b_box = np.array([0.45, 0.45, 0.55, 0.55], dtype=np.float32)
    boxes = ops.add(ops.matmul(gap, ops.constant(w_box), transpose_a=False, transpose_b=False), ops.constant(b_box))
    res_box = ops.result(boxes, name="defect_bbox")

    # Head 3: Defect Confidence Score [0.0 - 1.0]
    w_conf = np.random.randn(64, 1).astype(np.float32) * 0.05
    b_conf = np.array([0.95], dtype=np.float32)
    conf = ops.sigmoid(ops.add(ops.matmul(gap, ops.constant(w_conf), transpose_a=False, transpose_b=False), ops.constant(b_conf)))
    res_conf = ops.result(conf, name="confidence")

    # Construct OpenVINO Model
    model = ov.Model(
        results=[res_cls, res_box, res_conf],
        parameters=[data_input],
        name="AMAI_Edge_Defect_Detector_v1",
    )

    # Save to OpenVINO IR format
    ov.save_model(model, output_xml_path)
    return output_xml_path, bin_path


if __name__ == "__main__":
    assets_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
    xml_file = os.path.join(assets_dir, "defect_detector.xml")
    out_xml, out_bin = build_and_export_ov_model(xml_file)
    print(f"Exported OpenVINO IR Model to:\n  {out_xml}\n  {out_bin}")
