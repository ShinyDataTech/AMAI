"""Intel OpenVINO latency and throughput benchmarking harness."""

import os
import sys
import time
from typing import Dict, List

# Ensure project root in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import openvino as ov

from inference.detector import OpenVINODetector


def run_benchmark(num_iterations: int = 100) -> Dict[str, float]:
    """Runs high-precision inference benchmark measuring P50, P95, P99, and FPS."""
    core = ov.Core()
    devices = core.available_devices
    print(f"============================================================")
    print(f"   INTEL OPENVINO EDGE INFERENCE BENCHMARK")
    print(f"============================================================")
    print(f"OpenVINO Version : {ov.__version__}")
    print(f"Available Devices: {devices}")

    detector = OpenVINODetector(device_name="AUTO")
    print(f"Active Device    : {detector.device}")

    # Generate synthetic camera frame [480, 640, 3]
    dummy_rgb = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    dummy_depth = np.full((480, 640), 0.42, dtype=np.float32)

    # Warmup
    print("Executing 10 warmup cycles...")
    for _ in range(10):
        detector.detect(dummy_rgb, dummy_depth)

    # Benchmark loop
    print(f"Running {num_iterations} benchmark iterations...")
    latencies: List[float] = []

    start_total = time.perf_counter()
    for _ in range(num_iterations):
        res = detector.detect(dummy_rgb, dummy_depth)
        latencies.append(res.inference_time_ms)
    end_total = time.perf_counter()

    latencies_arr = np.array(latencies)
    total_time_s = end_total - start_total
    fps = num_iterations / total_time_s

    metrics = {
        "mean_ms": float(np.mean(latencies_arr)),
        "min_ms": float(np.min(latencies_arr)),
        "max_ms": float(np.max(latencies_arr)),
        "p50_ms": float(np.percentile(latencies_arr, 50)),
        "p95_ms": float(np.percentile(latencies_arr, 95)),
        "p99_ms": float(np.percentile(latencies_arr, 99)),
        "fps": float(fps),
    }

    print("------------------------------------------------------------")
    print(f"Mean Latency     : {metrics['mean_ms']:.2f} ms")
    print(f"Median (P50)     : {metrics['p50_ms']:.2f} ms")
    print(f"P95 Latency      : {metrics['p95_ms']:.2f} ms")
    print(f"P99 Latency      : {metrics['p99_ms']:.2f} ms")
    print(f"Min / Max        : {metrics['min_ms']:.2f} ms / {metrics['max_ms']:.2f} ms")
    print(f"Throughput       : {metrics['fps']:.1f} FPS")
    print("------------------------------------------------------------")
    if metrics["p95_ms"] < 30.0:
        print("SUCCESS: Latency satisfies <30ms edge micro-assembly constraint!")
    else:
        print("WARNING: Latency exceeded 30ms budget.")
    print("============================================================\n")

    return metrics


if __name__ == "__main__":
    run_benchmark(num_iterations=100)
