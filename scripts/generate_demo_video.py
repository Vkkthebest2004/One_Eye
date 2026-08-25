import os
import math
import numpy as np
import cv2
from pathlib import Path

def create_factory_demo_video(
    output_path: str = "./videos/demo/factory_safety.mp4",
    duration_sec: int = 15,
    fps: int = 30,
    width: int = 1280,
    height: int = 720
):
    """
    Generates a realistic synthetic factory CCTV video with moving workers,
    heavy machinery, danger zones, and PPE state changes for offline testing.
    """
    out_dir = Path(output_path).parent
    out_dir.mkdir(parents=True, exist_ok=True)

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    total_frames = duration_sec * fps
    print(f"Generating {total_frames} frames ({duration_sec}s @ {fps}fps) to {output_path}...")

    # Define factory static layout
    floor_color = (40, 42, 45)
    line_color = (70, 75, 80)
    zone_poly = np.array([[200, 250], [580, 250], [640, 620], [150, 620]], np.int32)
    machine_box = (300, 280, 220, 200) # x, y, w, h

    for frame_idx in range(total_frames):
        t = frame_idx / float(fps)
        img = np.full((height, width, 3), floor_color, dtype=np.uint8)

        # Draw floor grid lines (perspective look)
        for gy in range(150, height, 80):
            cv2.line(img, (0, gy), (width, gy), line_color, 1)
        for gx in range(0, width, 120):
            cv2.line(img, (gx, 150), (int(gx * 1.2), height), line_color, 1)

        # Draw Restricted Zone Polygon with hatched boundary
        zone_overlay = img.copy()
        cv2.fillPoly(zone_overlay, [zone_poly], (20, 30, 80)) # Dark Red/Orange tint
        cv2.addWeighted(zone_overlay, 0.4, img, 0.6, 0, img)
        cv2.polylines(img, [zone_poly], True, (0, 140, 255), 2, cv2.LINE_AA)
        cv2.putText(img, "RESTRICTED DANGER ZONE", (zone_poly[0][0] + 20, zone_poly[0][1] + 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 160, 255), 2)

        # Draw Heavy Machine (Hydraulic Stamping Press)
        mx, my, mw, mh = machine_box
        cv2.rectangle(img, (mx, my), (mx + mw, my + mh), (60, 65, 75), -1)
        cv2.rectangle(img, (mx, my), (mx + mw, my + mh), (120, 130, 145), 3)
        # Machine control panel
        cv2.rectangle(img, (mx + 20, my + 30), (mx + mw - 20, my + 90), (30, 30, 35), -1)
        # Pulsing status light on machine
        light_color = (0, 0, 240) if int(t * 3) % 2 == 0 else (0, 180, 0)
        cv2.circle(img, (mx + mw - 30, my + 50), 10, light_color, -1)
        cv2.putText(img, "HYDRAULIC PRESS #01", (mx + 25, my + 130), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 2)
        cv2.putText(img, "STATUS: ACTIVE", (mx + 25, my + 160), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 220, 0), 1)

        # Simulated Worker 1 (Worker #07) - Approaches Machine Zone
        # Moves horizontally and vertically in a loop
        w1_base_x = 750 - int(math.sin(t * 0.5) * 450)
        w1_base_y = 480 + int(math.cos(t * 0.5) * 80)
        w1_w, w1_h = 75, 170
        w1_x1, w1_y1 = w1_base_x - w1_w // 2, w1_base_y - w1_h
        w1_x2, w1_y2 = w1_base_x + w1_w // 2, w1_base_y

        # Draw Worker 1 (Worker #07)
        # Torso / Vest
        cv2.rectangle(img, (w1_x1, w1_y1 + 45), (w1_x2, w1_y2 - 50), (45, 50, 180), -1) # Blue overalls
        # Head
        head_center = (w1_base_x, w1_y1 + 25)
        cv2.circle(img, head_center, 18, (140, 180, 210), -1) # Skin tone
        # Helmet missing simulation on Worker 1 after t > 4s
        if t <= 4.0 or t > 12.0:
            # Yellow hardhat
            cv2.ellipse(img, (head_center[0], head_center[1] - 8), (20, 14), 0, 180, 360, (0, 220, 240), -1)
        # Legs
        cv2.line(img, (w1_base_x - 15, w1_y2 - 50), (w1_base_x - 15, w1_y2), (30, 35, 120), 10)
        cv2.line(img, (w1_base_x + 15, w1_y2 - 50), (w1_base_x + 15, w1_y2), (30, 35, 120), 10)

        # Simulated Worker 2 (Worker #03) - Safe area worker with full PPE
        w2_base_x = 950 + int(math.cos(t * 0.7) * 80)
        w2_base_y = 380 + int(math.sin(t * 0.7) * 40)
        w2_w, w2_h = 60, 140
        w2_x1, w2_y1 = w2_base_x - w2_w // 2, w2_base_y - w2_h
        w2_x2, w2_y2 = w2_base_x + w2_w // 2, w2_base_y

        # High-vis neon green safety vest on Worker 2
        cv2.rectangle(img, (w2_x1, w2_y1 + 35), (w2_x2, w2_y2 - 40), (40, 210, 80), -1)
        # Head with White Hardhat
        cv2.circle(img, (w2_base_x, w2_y1 + 20), 15, (140, 180, 210), -1)
        cv2.ellipse(img, (w2_base_x, w2_y1 + 12), (18, 12), 0, 180, 360, (240, 240, 240), -1)
        # Legs
        cv2.line(img, (w2_base_x - 12, w2_y2 - 40), (w2_base_x - 12, w2_y2), (40, 40, 45), 8)
        cv2.line(img, (w2_base_x + 12, w2_y2 - 40), (w2_base_x + 12, w2_y2), (40, 40, 45), 8)

        # Top CCTV HUD timestamp banner
        cv2.putText(img, f"CAM_01 | NORTH PLANT | 2026-08-25 08:30:{int(t):02d} | 30 FPS",
                    (25, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 200), 2)
        cv2.putText(img, "ONE EYE INDUSTRIAL INTELLIGENCE - DEMO FEED", (width - 490, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180, 180, 180), 1)

        writer.write(img)

    writer.release()
    print(f"Successfully generated factory demo video: {output_path}")

if __name__ == "__main__":
    create_factory_demo_video()
