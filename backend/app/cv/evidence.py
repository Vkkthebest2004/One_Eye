import os
import datetime
import logging
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any
import numpy as np
import cv2

logger = logging.getLogger(__name__)


class EvidenceManager:
    """
    Evidence Capture & Annotation Engine.
    Saves forensic image snapshots with overlay metadata into structured dated directories.
    """
    def __init__(self, base_dir: str = "./evidence"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def capture_snapshot(
        self,
        frame: np.ndarray,
        event_id: str,
        camera_id: str,
        worker_id: Optional[int],
        hazard_types: List[str],
        risk_score: int,
        severity: str,
        highlight_bbox: Optional[Tuple[float, float, float, float]] = None
    ) -> Tuple[str, str]:
        """
        Annotates and saves an evidence frame.
        Returns (relative_web_path, absolute_file_path).
        """
        now = datetime.datetime.utcnow()
        date_dir = self.base_dir / f"{now.year:04d}" / f"{now.month:02d}" / f"{now.day:02d}"
        date_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{event_id}.jpg"
        file_path = date_dir / filename
        relative_path = f"/evidence/{now.year:04d}/{now.month:02d}/{now.day:02d}/{filename}"

        if frame is None or frame.size == 0:
            logger.warning(f"Empty frame passed for evidence capture {event_id}")
            return relative_path, str(file_path)

        try:
            annotated = frame.copy()
            h, w = annotated.shape[:2]

            # Determine severity color (BGR)
            sev_upper = severity.upper()
            if sev_upper == "CRITICAL":
                color = (0, 0, 230) # Bright Red
            elif sev_upper == "HIGH":
                color = (0, 140, 255) # Orange
            elif sev_upper == "MEDIUM":
                color = (0, 215, 255) # Yellow-Orange
            else:
                color = (0, 220, 0) # Green

            # Draw highlight bounding box if available
            if highlight_bbox:
                x1, y1, x2, y2 = [int(v) for v in highlight_bbox]
                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 3)
                # Worker tag
                tag = f"Worker #{worker_id:02d}" if worker_id is not None else "Target"
                cv2.putText(annotated, tag, (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

            # Draw top forensic banner
            banner_height = 45
            overlay = annotated.copy()
            cv2.rectangle(overlay, (0, 0), (w, banner_height), (20, 20, 20), -1)
            cv2.addWeighted(overlay, 0.75, annotated, 0.25, 0, annotated)

            # Banner text
            time_str = now.strftime("%Y-%m-%d %H:%M:%S UTC")
            header_text = f"ONE EYE EVIDENCE | {event_id} | CAM: {camera_id} | {time_str}"
            cv2.putText(annotated, header_text, (15, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

            # Risk & Severity badge on top-right
            badge_text = f"{severity} (RISK {risk_score}/100)"
            (tw, th), _ = cv2.getTextSize(badge_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            badge_x = w - tw - 20
            cv2.rectangle(annotated, (badge_x - 10, 8), (w - 10, 38), color, -1)
            cv2.putText(annotated, badge_text, (badge_x, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)

            # Bottom hazard summary banner
            hazards_str = " | ".join(hazard_types)
            bot_y = h - 15
            cv2.rectangle(annotated, (0, h - 35), (w, h), (15, 15, 15), -1)
            cv2.putText(annotated, f"HAZARDS: {hazards_str}", (15, bot_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

            # Write image to disk
            cv2.imwrite(str(file_path), annotated)
            logger.info(f"Captured evidence snapshot for {event_id} -> {file_path}")
        except Exception as e:
            logger.error(f"Failed to capture evidence for {event_id}: {e}")

        return relative_path, str(file_path)
