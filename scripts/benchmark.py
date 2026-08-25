import time
import sys
import numpy as np
from pathlib import Path

# Add backend to sys.path
backend_path = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from app.cv.detector import Detector, Detection
from app.cv.tracker import MultiObjectTracker
from app.cv.ppe import PPEEngine
from app.cv.zones import ZoneEngine, ZoneDefinition
from app.cv.homography import HomographyCalibrator
from app.cv.proximity import ProximityEngine, MachineDefinition
from app.cv.exposure import ExposureTracker
from app.risk.engine import RiskEngine


def benchmark_pipeline(iterations: int = 50):
    print("=" * 65)
    print("      ONE EYE INDUSTRIAL SAFETY PLATFORM — LATENCY BENCHMARK")
    print("=" * 65)

    frame = np.full((720, 1280, 3), 40, dtype=np.uint8)

    # 1. Benchmark Detector
    detector = Detector(model_path="yolov8n.pt", device="cpu")
    det_times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        _ = detector.predict(frame)
        det_times.append((time.perf_counter() - t0) * 1000)

    # 2. Benchmark Tracker
    tracker = MultiObjectTracker()
    sim_dets = [
        Detection(0, "person", 0.92, 300, 200, 380, 480, 340, 340, 340, 480),
        Detection(0, "person", 0.88, 600, 220, 670, 450, 635, 335, 635, 450)
    ]
    track_times = []
    for i in range(iterations):
        t0 = time.perf_counter()
        _ = tracker.update(sim_dets, time.time() + i * 0.033)
        track_times.append((time.perf_counter() - t0) * 1000)

    # 3. Benchmark Spatial Reasoning (Zones + Homography + Proximity)
    zone_engine = ZoneEngine()
    zone_engine.register_zone(ZoneDefinition(
        id="z1", name="Press Zone", camera_id="CAM_01",
        polygon_points=[(200, 250), (580, 250), (640, 620), (150, 620)]
    ))
    prox_engine = ProximityEngine()
    prox_engine.register_machine(MachineDefinition(
        id="m1", name="Press", camera_id="CAM_01",
        bbox=(300, 280, 520, 480), center=(410, 380), danger_radius_m=1.5
    ))
    calibrator = HomographyCalibrator("CAM_01")
    calibrator.calibrate(
        [(200, 250), (580, 250), (640, 620), (150, 620)],
        [(0, 0), (6.0, 0), (6.0, 8.0), (0, 8.0)]
    )

    spatial_times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        _ = zone_engine.evaluate_worker(1, 350.0, 450.0, time.time(), "CAM_01")
        _ = prox_engine.evaluate_worker(1, (350.0, 450.0), "CAM_01", calibrator)
        spatial_times.append((time.perf_counter() - t0) * 1000)

    # 4. Benchmark Compound Risk Engine
    risk_engine = RiskEngine()
    risk_times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        _ = risk_engine.evaluate(
            worker_id=1,
            active_hazards=["NO_HELMET", "RESTRICTED_ZONE", "UNSAFE_PROXIMITY_CRITICAL"],
            exposure_duration_sec=8.4,
            proximity_distance_m=1.1,
            detection_confidence=0.95
        )
        risk_times.append((time.perf_counter() - t0) * 1000)

    # Summary Table
    avg_det = np.mean(det_times)
    avg_trk = np.mean(track_times)
    avg_spatial = np.mean(spatial_times)
    avg_risk = np.mean(risk_times)
    total_pipeline_ms = avg_det + avg_trk + avg_spatial + avg_risk
    estimated_fps = 1000.0 / total_pipeline_ms if total_pipeline_ms > 0 else 0

    print(f"{'Subsystem':<35} | {'Avg Latency (ms)':<18} | {'P95 Latency (ms)'}")
    print("-" * 65)
    print(f"{'Perception / YOLO Inference':<35} | {avg_det:>14.2f} ms | {np.percentile(det_times, 95):>12.2f} ms")
    print(f"{'Multi-Object Tracking (ByteTrack)':<35} | {avg_trk:>14.2f} ms | {np.percentile(track_times, 95):>12.2f} ms")
    print(f"{'Spatial Reasoning (Zones/Prox/Homo)':<35} | {avg_spatial:>14.2f} ms | {np.percentile(spatial_times, 95):>12.2f} ms")
    print(f"{'Compound 0-100 Risk Engine':<35} | {avg_risk:>14.2f} ms | {np.percentile(risk_times, 95):>12.2f} ms")
    print("-" * 65)
    print(f"{'TOTAL CORE PIPELINE':<35} | {total_pipeline_ms:>14.2f} ms | ~{estimated_fps:>5.1f} FPS")
    print("=" * 65)


if __name__ == "__main__":
    benchmark_pipeline()
