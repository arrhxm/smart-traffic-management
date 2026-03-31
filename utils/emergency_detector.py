# ============================================================
#  utils/emergency_detector.py
#  Emergency Vehicle Detection & Alert Management
# ============================================================

import time
import threading
from collections import defaultdict
from utils.logger import setup_logger

logger = setup_logger("emergency_detector")

ALERT_COOLDOWN = 30   # seconds before re-alerting the same lane


class EmergencyDetector:
    """
    Tracks emergency vehicle detections across lanes and manages alerts.

    Integrates with:
      - VehicleDetector  (sets per-lane emergency flags)
      - TrafficController (reads flags to prioritise green)
      - Frontend          (provides alert status via /api/emergency)
    """

    def __init__(self):
        self._lane_flags: dict[int, bool]  = defaultdict(bool)
        self._alert_times: dict[int, float] = {}   # lane_id → last alert timestamp
        self._history: list[dict]           = []   # log of all detected events
        self._lock = threading.Lock()

    def update(self, lane_emergency: dict[int, bool]):
        """
        Called every tick with the latest per-lane emergency flags.
        Logs new events and triggers alert logic.
        """
        with self._lock:
            for lane_id, detected in lane_emergency.items():
                was_detected = self._lane_flags[lane_id]
                self._lane_flags[lane_id] = detected

                # Rising edge — new detection
                if detected and not was_detected:
                    self._on_emergency_detected(lane_id)

                # Falling edge — vehicle cleared
                elif not detected and was_detected:
                    self._on_emergency_cleared(lane_id)

    def get_status(self) -> dict:
        """Return current emergency status for all lanes."""
        with self._lock:
            return {
                "active_lanes": [
                    lid for lid, flag in self._lane_flags.items() if flag
                ],
                "lane_flags":   dict(self._lane_flags),
                "recent_events": self._history[-10:],   # last 10 events
                "timestamp":    time.time(),
            }

    def is_emergency_active(self, lane_id: int) -> bool:
        with self._lock:
            return self._lane_flags.get(lane_id, False)

    def any_emergency_active(self) -> bool:
        with self._lock:
            return any(self._lane_flags.values())

    # ── Private ───────────────────────────────────────────────

    def _on_emergency_detected(self, lane_id: int):
        now = time.time()
        last = self._alert_times.get(lane_id, 0)
        if now - last > ALERT_COOLDOWN:
            self._alert_times[lane_id] = now
            logger.warning(f"🚨 Emergency vehicle detected on Lane {lane_id + 1}!")
            self._log_event(lane_id, "DETECTED")

    def _on_emergency_cleared(self, lane_id: int):
        logger.info(f"✅ Emergency cleared on Lane {lane_id + 1}.")
        self._log_event(lane_id, "CLEARED")

    def _log_event(self, lane_id: int, event_type: str):
        self._history.append({
            "lane_id":    lane_id,
            "event":      event_type,
            "timestamp":  time.time(),
            "time_str":   time.strftime("%H:%M:%S"),
        })
        # Keep history bounded
        if len(self._history) > 200:
            self._history = self._history[-200:]
