# ============================================================
#  utils/vehicle_detector.py
#  YOLOv8 vehicle detection — with per-lane count caching
# ============================================================

import cv2
import numpy as np
import threading
from collections import deque
from utils.logger import setup_logger

logger = setup_logger("vehicle_detector")

# COCO class IDs for vehicles
VEHICLE_CLASSES = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}

EMERGENCY_KEYWORDS = ["ambulance", "fire truck", "police"]

BOX_COLORS = {
    "car":        (0, 200, 255),
    "motorcycle": (200, 100, 0),
    "bus":        (50, 205, 50),
    "truck":      (255, 140, 0),
    "ambulance":  (0, 0, 255),
}


class VehicleDetector:
    """
    YOLOv8 vehicle detector with per-lane count caching.
    Thread-safe: capture threads write counts,
    management loop reads them via get_latest_count().
    """

    def __init__(self,
                 model_path: str = "models/yolov8n.pt",
                 confidence: float = 0.4,
                 iou_threshold: float = 0.45,
                 img_size: int = 416):

        self.confidence    = confidence
        self.iou_threshold = iou_threshold
        self.img_size      = img_size
        self._lock         = threading.Lock()

        # Per-lane state
        self._counts:    dict[int, int]  = {}
        self._emergency: dict[int, bool] = {}
        self._history:   dict[int, deque] = {}

        logger.info(f"Loading YOLO model from: {model_path}")
        try:
            from ultralytics import YOLO
            self.model = YOLO(model_path)
            logger.info("YOLO model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
            self.model = None

    # ── Public API ────────────────────────────────────────────

    def detect(self, frame: np.ndarray, lane_id: int) -> tuple[int, bool]:
        """Detect vehicles, cache count, return (count, has_emergency)."""
        if self.model is None:
            return 0, False

        results   = self._infer(frame)
        boxes     = self._filter(results)
        emergency = self._is_emergency(results)
        count     = self._smooth(lane_id, len(boxes))

        with self._lock:
            self._counts[lane_id]    = count
            self._emergency[lane_id] = emergency

        return count, emergency

    def detect_and_annotate(self,
                             frame: np.ndarray,
                             lane_id: int) -> tuple[np.ndarray, int, bool]:
        """Detect, annotate frame, cache count. Returns (frame, count, emergency)."""
        if self.model is None:
            return frame, 0, False

        results   = self._infer(frame)
        boxes     = self._filter(results)
        emergency = self._is_emergency(results)
        count     = self._smooth(lane_id, len(boxes))

        with self._lock:
            self._counts[lane_id]    = count
            self._emergency[lane_id] = emergency

        annotated = self._draw(frame.copy(), boxes)
        return annotated, count, emergency

    def get_latest_count(self, lane_id: int):
        """Return the last cached count for this lane (or None if not yet set)."""
        with self._lock:
            return self._counts.get(lane_id, None)

    def get_latest_emergency(self, lane_id: int):
        """Return the last cached emergency flag for this lane."""
        with self._lock:
            return self._emergency.get(lane_id, False)

    # ── Internals ─────────────────────────────────────────────

    def _infer(self, frame):
        return self.model(
            frame,
            conf=self.confidence,
            iou=self.iou_threshold,
            imgsz=self.img_size,
            verbose=False,
        )

    def _filter(self, results) -> list:
        boxes = []
        for r in results:
            for box in r.boxes:
                cls_id = int(box.cls[0])
                if cls_id in VEHICLE_CLASSES:
                    boxes.append({
                        "cls_id": cls_id,
                        "label":  VEHICLE_CLASSES[cls_id],
                        "conf":   float(box.conf[0]),
                        "xyxy":   box.xyxy[0].tolist(),
                    })
        return boxes

    def _is_emergency(self, results) -> bool:
        for r in results:
            for box in r.boxes:
                cls_id = int(box.cls[0])
                label  = self.model.names.get(cls_id, "").lower()
                if any(kw in label for kw in EMERGENCY_KEYWORDS):
                    return True
        return False

    def _draw(self, frame: np.ndarray, boxes: list) -> np.ndarray:
        for b in boxes:
            x1, y1, x2, y2 = map(int, b["xyxy"])
            color = BOX_COLORS.get(b["label"], (180, 180, 180))
            label = f"{b['label']} {b['conf']:.2f}"

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
            cv2.rectangle(frame, (x1, y1 - th - 6), (x1 + tw + 4, y1), color, -1)
            cv2.putText(frame, label, (x1 + 2, y1 - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1)
        return frame

    def _smooth(self, lane_id: int, raw: int, window: int = 3) -> int:
        hist = self._history.setdefault(lane_id, deque(maxlen=window))
        hist.append(raw)
        return int(round(sum(hist) / len(hist)))
