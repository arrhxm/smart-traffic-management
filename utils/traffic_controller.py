# ============================================================
#  utils/traffic_controller.py
#  Adaptive Traffic Signal Controller
# ============================================================

import time
import threading
import numpy as np
from collections import deque
from utils.logger import setup_logger

logger = setup_logger("traffic_controller")

# Signal states
GREEN  = "GREEN"
YELLOW = "YELLOW"
RED    = "RED"

# Timing constants (seconds)
MIN_GREEN_TIME   = 10    # minimum green duration regardless of density
MAX_GREEN_TIME   = 60    # maximum green duration
YELLOW_TIME      = 3     # fixed yellow phase
MIN_RED_TIME     = 5     # minimum red before re-evaluation
EMERGENCY_GREEN  = 20    # forced green time for emergency lane


class LaneState:
    """Holds real-time state for a single lane."""

    def __init__(self, lane_id: int):
        self.lane_id         = lane_id
        self.vehicle_count   = 0
        self.density         = 0.0          # 0.0 – 1.0
        self.signal          = RED
        self.green_time      = MIN_GREEN_TIME
        self.time_remaining  = 0
        self.has_emergency   = False
        self.count_history   = deque(maxlen=10)  # last 10 readings
        self.wait_time       = 0             # cumulative wait (seconds)

    def update_density(self, count: int, max_vehicles: int = 30):
        """Compute normalised density from raw count."""
        self.vehicle_count = count
        self.count_history.append(count)
        avg = np.mean(self.count_history) if self.count_history else count
        self.density = min(avg / max_vehicles, 1.0)

    def compute_green_time(self) -> float:
        """
        Adaptive green time calculation:
            green_time = MIN + density × (MAX - MIN)
        Emergency vehicles always get MAX green time.
        """
        if self.has_emergency:
            return EMERGENCY_GREEN
        t = MIN_GREEN_TIME + self.density * (MAX_GREEN_TIME - MIN_GREEN_TIME)
        return round(t, 1)

    def to_dict(self) -> dict:
        return {
            "lane_id":       self.lane_id,
            "vehicle_count": self.vehicle_count,
            "density":       round(self.density, 3),
            "density_pct":   round(self.density * 100, 1),
            "signal":        self.signal,
            "green_time":    self.green_time,
            "time_remaining": round(self.time_remaining, 1),
            "has_emergency": self.has_emergency,
            "wait_time":     round(self.wait_time, 1),
        }


class TrafficController:
    """
    Manages traffic signals for N lanes using density-based adaptive timing.

    Algorithm (round-robin with density weighting):
      1. Rank lanes by density (descending) each cycle.
      2. Grant green to the highest-density lane first.
      3. Emergency lanes jump to the front of the queue.
      4. Yellow phase separates every GREEN→RED transition.
    """

    def __init__(self, num_lanes: int = 4):
        self.num_lanes     = num_lanes
        self.lanes         = {i: LaneState(i) for i in range(num_lanes)}
        self.current_phase = 0          # which lane is currently GREEN
        self.phase_start   = time.time()
        self.phase_stage   = GREEN      # GREEN | YELLOW
        self._lock         = threading.Lock()
        self._stats        = {i: {"total_vehicles": 0, "green_cycles": 0}
                               for i in range(num_lanes)}
        logger.info(f"TrafficController initialised with {num_lanes} lanes.")

    # ── Public API ────────────────────────────────────────────

    def update(self, lane_counts: dict[int, int], lane_emergency: dict[int, bool]):
        """
        Called every tick (≈1 s) with new detection results.
        Updates densities and advances the signal phase if needed.
        """
        with self._lock:
            # Update each lane's state
            for lane_id, count in lane_counts.items():
                lane = self.lanes[lane_id]
                lane.update_density(count)
                lane.has_emergency = lane_emergency.get(lane_id, False)
                self._stats[lane_id]["total_vehicles"] += count

            # Advance time
            elapsed       = time.time() - self.phase_start
            current_lane  = self.lanes[self.current_phase]
            green_needed  = current_lane.compute_green_time()

            if self.phase_stage == GREEN:
                current_lane.time_remaining = max(green_needed - elapsed, 0)

                # Check for emergency in another lane
                emergency_lane = self._find_emergency_lane()
                if emergency_lane is not None and emergency_lane != self.current_phase:
                    logger.info(f"Emergency detected on lane {emergency_lane}! Switching.")
                    self._start_yellow()
                elif elapsed >= green_needed:
                    self._start_yellow()

            elif self.phase_stage == YELLOW:
                current_lane.time_remaining = max(YELLOW_TIME - elapsed, 0)
                if elapsed >= YELLOW_TIME:
                    self._advance_phase()

            # Accumulate wait time for red lanes
            for lane_id, lane in self.lanes.items():
                if lane.signal == RED:
                    lane.wait_time += 1
                else:
                    lane.wait_time = 0

    def get_signal_state(self, lane_id: int) -> str:
        with self._lock:
            return self.lanes[lane_id].signal

    def get_signal_states(self) -> dict[int, str]:
        with self._lock:
            return {lid: l.signal for lid, l in self.lanes.items()}

    def get_all_lane_status(self) -> list[dict]:
        with self._lock:
            return [l.to_dict() for l in self.lanes.values()]

    def get_statistics(self) -> dict:
        with self._lock:
            return {
                "per_lane": self._stats,
                "timestamp": time.time(),
            }

    # ── Internal Phase Management ─────────────────────────────

    def _start_yellow(self):
        """Transition the current GREEN lane to YELLOW."""
        self.lanes[self.current_phase].signal = YELLOW
        self.phase_stage = YELLOW
        self.phase_start = time.time()
        logger.debug(f"Lane {self.current_phase} → YELLOW")

    def _advance_phase(self):
        """
        After yellow, move to the next phase.
        Chooses the lane with highest density (emergency takes priority).
        """
        # Set current lane to RED
        self.lanes[self.current_phase].signal = RED

        # Select next lane
        next_lane = self._select_next_lane()
        self.current_phase = next_lane

        # Activate next lane's green
        lane = self.lanes[next_lane]
        lane.signal     = GREEN
        lane.green_time = lane.compute_green_time()
        self.phase_stage = GREEN
        self.phase_start = time.time()
        self._stats[next_lane]["green_cycles"] += 1

        logger.info(
            f"Lane {next_lane} → GREEN "
            f"(density={lane.density:.2f}, green_time={lane.green_time}s)"
        )

    def _select_next_lane(self) -> int:
        """
        Priority order:
          1. Any lane with an emergency vehicle
          2. Lane with highest density (excluding current)
          3. Round-robin fallback
        """
        # Emergency first
        em = self._find_emergency_lane()
        if em is not None:
            return em

        # Sort by density, skip current
        candidates = sorted(
            [i for i in range(self.num_lanes) if i != self.current_phase],
            key=lambda i: self.lanes[i].density,
            reverse=True,
        )
        return candidates[0] if candidates else (self.current_phase + 1) % self.num_lanes

    def _find_emergency_lane(self) -> int | None:
        """Return first lane with an emergency vehicle, or None."""
        for lane_id, lane in self.lanes.items():
            if lane.has_emergency:
                return lane_id
        return None
