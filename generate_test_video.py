# ============================================================
#  generate_test_video.py
#  Generates 4 realistic synthetic traffic lane videos
#  No internet or camera needed.
#  Run: python generate_test_video.py
# ============================================================

import cv2
import numpy as np
import os
import random
import math

os.makedirs("test_videos", exist_ok=True)

WIDTH, HEIGHT = 640, 480
FPS           = 24
DURATION_SEC  = 40   # seconds per video


# ── Helpers ───────────────────────────────────────────────────

def rand_color():
    palettes = [
        (220,  60,  60),  # red
        ( 60, 120, 220),  # blue
        ( 60, 200,  80),  # green
        (220, 200,  50),  # yellow
        (200, 200, 200),  # white
        (120,  80,  40),  # brown
        ( 80,  80,  80),  # dark grey
        (240, 140,  40),  # orange
    ]
    c = random.choice(palettes)
    # slight variation
    return tuple(max(0, min(255, v + random.randint(-20, 20))) for v in c)


def draw_road(frame):
    """Draw a 2-lane road on the frame."""
    road_top, road_bot = 120, HEIGHT - 60

    # Asphalt
    cv2.rectangle(frame, (0, road_top), (WIDTH, road_bot), (55, 55, 55), -1)

    # Road edges (white lines)
    cv2.line(frame, (0, road_top),     (WIDTH, road_top),     (200, 200, 200), 3)
    cv2.line(frame, (0, road_bot),     (WIDTH, road_bot),     (200, 200, 200), 3)

    # Centre dashed line
    lane_y = (road_top + road_bot) // 2
    for x in range(0, WIDTH, 60):
        cv2.line(frame, (x, lane_y), (x + 35, lane_y), (220, 220, 80), 2)

    # Pavement / grass
    cv2.rectangle(frame, (0, 0),        (WIDTH, road_top),     (34, 85, 34),  -1)
    cv2.rectangle(frame, (0, road_bot), (WIDTH, HEIGHT),        (34, 85, 34),  -1)

    # Sidewalk strips
    cv2.rectangle(frame, (0, road_top - 18), (WIDTH, road_top),     (160, 140, 110), -1)
    cv2.rectangle(frame, (0, road_bot),      (WIDTH, road_bot + 18),(160, 140, 110), -1)


def draw_car(frame, x, y, w, h, color, direction=1):
    """
    Draw a simple top-down car.
    direction: 1 = moving right, -1 = moving left
    """
    x, y, w, h = int(x), int(y), int(w), int(h)

    # Body
    cv2.rectangle(frame, (x, y), (x + w, y + h), color, -1)

    # Roof (darker centre rectangle)
    roof_margin_x = w // 5
    roof_margin_y = h // 5
    roof_color = tuple(max(0, v - 50) for v in color)
    cv2.rectangle(frame,
                  (x + roof_margin_x,     y + roof_margin_y),
                  (x + w - roof_margin_x, y + h - roof_margin_y),
                  roof_color, -1)

    # Windshield (light blue tint)
    ws_color = (180, 220, 240)
    if direction == 1:
        cv2.rectangle(frame, (x + w - w//3, y + 4), (x + w - 4, y + h - 4), ws_color, -1)
    else:
        cv2.rectangle(frame, (x + 4, y + 4), (x + w//3, y + h - 4), ws_color, -1)

    # Wheels (4 dark circles)
    wheel_r = max(4, h // 5)
    wheel_color = (20, 20, 20)
    for wx, wy in [(x + wheel_r, y - wheel_r // 2),
                   (x + w - wheel_r, y - wheel_r // 2),
                   (x + wheel_r, y + h + wheel_r // 2 - 2),
                   (x + w - wheel_r, y + h + wheel_r // 2 - 2)]:
        cv2.circle(frame, (wx, wy), wheel_r, wheel_color, -1)

    # Headlights
    light_color = (255, 255, 180) if direction == 1 else (255, 80, 80)
    lx = x + w - 4 if direction == 1 else x + 4
    cv2.rectangle(frame, (lx - 3, y + 3), (lx + 3, y + h // 3), light_color, -1)
    cv2.rectangle(frame, (lx - 3, y + h - h//3), (lx + 3, y + h - 3), light_color, -1)


def draw_ambulance(frame, x, y, w, h, direction=1):
    """Draw a white ambulance with red cross."""
    draw_car(frame, x, y, w, h, (230, 230, 230), direction)
    # Red cross
    cx, cy = int(x + w // 2), int(y + h // 2)
    cv2.rectangle(frame, (cx - 2, cy - 8), (cx + 2, cy + 8), (0, 0, 220), -1)
    cv2.rectangle(frame, (cx - 8, cy - 2), (cx + 8, cy + 2), (0, 0, 220), -1)
    # Siren flash (alternates each frame — just draw blue/red bar)
    siren = (0, 0, 255) if (int(x) % 20 < 10) else (255, 0, 0)
    cv2.rectangle(frame, (int(x) + 4, int(y) - 5), (int(x) + w - 4, int(y)), siren, -1)


class Car:
    ROAD_TOP = 135
    ROAD_BOT = HEIGHT - 75

    def __init__(self, lane=0, emergency=False):
        self.emergency = emergency
        self.lane      = lane   # 0 = upper lane (right), 1 = lower lane (left)
        self.direction = 1 if lane == 0 else -1

        self.w = random.randint(55, 85)
        self.h = random.randint(28, 42)

        lane_mid  = self.ROAD_TOP + (self.ROAD_BOT - self.ROAD_TOP) // 4
        lane2_mid = self.ROAD_TOP + 3 * (self.ROAD_BOT - self.ROAD_TOP) // 4
        lane_y    = lane_mid if lane == 0 else lane2_mid
        self.y    = lane_y - self.h // 2 + random.randint(-6, 6)

        if self.direction == 1:
            self.x = random.randint(-WIDTH, 0)
        else:
            self.x = random.randint(WIDTH, 2 * WIDTH)

        self.speed = random.uniform(2.5, 6.5) if not emergency else random.uniform(7, 10)
        self.color = (230, 230, 230) if emergency else rand_color()

    def update(self):
        self.x += self.speed * self.direction

    def is_off_screen(self):
        if self.direction == 1:
            return self.x > WIDTH + 100
        else:
            return self.x < -200

    def draw(self, frame):
        if self.emergency:
            draw_ambulance(frame, self.x, self.y, self.w, self.h, self.direction)
        else:
            draw_car(frame, self.x, self.y, self.w, self.h, self.color, self.direction)


def generate_video(path, num_cars, has_emergency=False, density_pattern="normal"):
    """
    Generate one traffic lane video.

    density_pattern: "normal" | "heavy" | "light" | "variable"
    """
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out    = cv2.VideoWriter(path, fourcc, FPS, (WIDTH, HEIGHT))

    total_frames = DURATION_SEC * FPS

    # Initialise cars spread across the road
    cars = []
    for i in range(num_cars):
        lane = i % 2
        car  = Car(lane=lane)
        car.x = random.randint(0, WIDTH)   # spread initially
        cars.append(car)

    # One emergency vehicle partway through
    em_car       = None
    em_frame_in  = total_frames // 3 if has_emergency else -1

    # Background trees (static)
    tree_positions = [(random.randint(0, WIDTH), random.randint(10, 100)) for _ in range(12)]

    for f in range(total_frames):

        frame = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
        frame[:] = (60, 110, 60)   # grass base

        # Sky strip
        frame[:80, :] = (135, 170, 210)

        # Static trees
        for tx, ty in tree_positions:
            cv2.circle(frame, (tx, ty + 20), 22, (30, 90, 30), -1)
            cv2.rectangle(frame, (tx - 3, ty + 18), (tx + 3, ty + 38), (80, 50, 20), -1)

        draw_road(frame)

        # Density variation
        if density_pattern == "variable":
            # Sine wave density: busy then quiet
            phase   = f / total_frames * 2 * math.pi
            density = 0.5 + 0.5 * math.sin(phase)
            target  = int(3 + density * (num_cars - 3))
            while len(cars) < target:
                cars.append(Car(lane=random.randint(0, 1)))
        elif density_pattern == "heavy":
            while len(cars) < num_cars + 4:
                cars.append(Car(lane=random.randint(0, 1)))

        # Spawn emergency vehicle
        if f == em_frame_in and has_emergency:
            em_car = Car(lane=0, emergency=True)
            em_car.x = -100
            em_car.speed = 8

        # Update & draw cars (sort by y so overlap looks natural)
        cars = [c for c in cars if not c.is_off_screen()]
        for c in sorted(cars, key=lambda c: c.y):
            c.update()
            c.draw(frame)

        # Respawn if needed
        while len(cars) < num_cars:
            cars.append(Car(lane=random.randint(0, 1)))

        # Emergency car
        if em_car:
            if em_car.is_off_screen():
                em_car = None
            else:
                em_car.update()
                em_car.draw(frame)

        # Frame counter (top-left, subtle)
        time_sec = f // FPS
        cv2.putText(frame, f"{time_sec:02d}s", (8, 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)

        out.write(frame)

    out.release()
    print(f"  ✅  {path}  ({num_cars} cars, {DURATION_SEC}s, {density_pattern})")


# ── Main ──────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n🎬  Generating synthetic traffic test videos...\n")

    configs = [
        # (filename,        cars, emergency, pattern)
        ("test_videos/lane1.mp4",  8,  False, "normal"),
        ("test_videos/lane2.mp4", 14,  False, "heavy"),
        ("test_videos/lane3.mp4",  4,  False, "light"),
        ("test_videos/lane4.mp4", 10,  True,  "variable"),  # has ambulance
    ]

    for path, cars, em, pattern in configs:
        generate_video(path, cars, has_emergency=em, density_pattern=pattern)

    print(f"\n🎉  All 4 videos saved to test_videos/")
    print("    Restart app.py to load them into the dashboard.\n")
