#!/usr/bin/env python3
# ============================================================
#  demo.py — Standalone Demo (no camera or YOLO model needed)
#  Run this to test the TrafficController logic in the terminal.
# ============================================================

import time
import random
from utils.traffic_controller import TrafficController
from utils.emergency_detector import EmergencyDetector
from utils.logger import setup_logger

logger = setup_logger("demo")

NUM_LANES   = 4
ITERATIONS  = 30   # how many ticks to simulate
TICK_DELAY  = 1.0  # seconds per tick

SIGNAL_ICONS = {
    "GREEN":  "🟢",
    "YELLOW": "🟡",
    "RED":    "🔴",
}


def simulate():
    """Simulate the traffic management loop with random vehicle counts."""
    controller = TrafficController(num_lanes=NUM_LANES)
    emergency  = EmergencyDetector()

    print("\n" + "=" * 60)
    print("  Smart Traffic Management System — Demo Mode")
    print("=" * 60 + "\n")

    for tick in range(1, ITERATIONS + 1):
        # Generate random vehicle counts and rare emergencies
        lane_counts    = {i: random.randint(0, 25) for i in range(NUM_LANES)}
        lane_emergency = {i: random.random() < 0.05 for i in range(NUM_LANES)}

        # Update subsystems
        emergency.update(lane_emergency)
        controller.update(lane_counts, lane_emergency)

        # Print status table
        print(f"  Tick {tick:02d}  |  Active Green → Lane {controller.current_phase + 1}")
        print(f"  {'Lane':<8} {'Signal':<10} {'Vehicles':<10} {'Density':<10} {'GreenTime':<12} {'Emergency'}")
        print(f"  {'-'*62}")

        for lane in controller.get_all_lane_status():
            em_flag  = "🚨 YES" if lane["has_emergency"] else "—"
            sig_icon = SIGNAL_ICONS.get(lane["signal"], "?")
            print(
                f"  Lane {lane['lane_id'] + 1:<3} "
                f"{sig_icon} {lane['signal']:<8} "
                f"{lane['vehicle_count']:<10} "
                f"{lane['density_pct']:>5.1f}%    "
                f"{lane['green_time']:>6.1f}s      "
                f"{em_flag}"
            )

        em_status = emergency.get_status()
        if em_status["active_lanes"]:
            active = ", ".join(f"Lane {l+1}" for l in em_status["active_lanes"])
            print(f"\n  ⚠️  Emergency Active: {active}")

        print()
        time.sleep(TICK_DELAY)

    print("=" * 60)
    print("  Demo complete.")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    simulate()
