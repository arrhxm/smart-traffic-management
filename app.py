# ============================================================
#  Smart AI-Based Traffic Management System
#  app.py — Fixed version with proper multi-lane streaming
# ============================================================

from flask import Flask, render_template, Response, jsonify, request
from flask_socketio import SocketIO, emit
import threading
import time
import cv2
import numpy as np

from utils.traffic_controller import TrafficController
from utils.emergency_detector import EmergencyDetector
from utils.logger import setup_logger

# ── App Setup ────────────────────────────────────────────────
app = Flask(__name__)
app.config['SECRET_KEY'] = 'smart-traffic-secret-key'

# Use threading mode (more stable than eventlet for video)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

logger = setup_logger("app")

# ── Global State ─────────────────────────────────────────────
from utils.vehicle_detector import VehicleDetector
detector           = VehicleDetector(model_path="models/yolov8n.pt")
emergency_detector = EmergencyDetector()
controller         = TrafficController(num_lanes=4)

VIDEO_SOURCES = {
    0: "test_videos/lane1.mp4",
    1: "test_videos/lane2.mp4",
    2: "test_videos/lane3.mp4",
    3: "test_videos/lane4.mp4",
}

system_running = False

# Per-lane latest JPEG frame (bytes) — written by background threads, read by stream routes
latest_frames = {0: None, 1: None, 2: None, 3: None}
frame_locks   = {i: threading.Lock() for i in range(4)}


# ── Background Frame-Capture Threads ─────────────────────────

def capture_lane(lane_id: int):
    """
    Runs in its own thread.
    Reads frames from the video file, runs detection, stores the
    latest JPEG in latest_frames[lane_id].
    """
    source = VIDEO_SOURCES[lane_id]
    cap    = cv2.VideoCapture(source)

    if not cap.isOpened():
        logger.warning(f"Lane {lane_id}: cannot open {source}")
        placeholder = make_placeholder(lane_id)
        with frame_locks[lane_id]:
            latest_frames[lane_id] = placeholder
        return

    logger.info(f"Lane {lane_id}: capture thread started -> {source}")

    while True:
        ret, frame = cap.read()
        if not ret:
            # Loop video
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        # Resize for consistent display
        frame = cv2.resize(frame, (640, 360))

        # Run YOLO detection & annotate
        try:
            annotated, count, has_emergency = detector.detect_and_annotate(frame, lane_id)
        except Exception:
            annotated = frame
            count, has_emergency = 0, False

        # Overlay signal HUD
        signal    = controller.get_signal_state(lane_id)
        annotated = overlay_signal_info(annotated, lane_id, count, signal, has_emergency)

        # Encode to JPEG
        ret2, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 75])
        if not ret2:
            continue

        with frame_locks[lane_id]:
            latest_frames[lane_id] = buf.tobytes()

        time.sleep(0.04)   # ~25 fps cap

    cap.release()


def make_placeholder(lane_id: int) -> bytes:
    """Create a dark placeholder frame with a No Feed message."""
    img = np.zeros((360, 640, 3), dtype=np.uint8)
    img[:] = (20, 30, 45)
    cv2.putText(img, f"Lane {lane_id + 1}", (250, 150),
                cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 200, 160), 2)
    cv2.putText(img, "No video source", (210, 200),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (120, 150, 180), 2)
    _, buf = cv2.imencode(".jpg", img)
    return buf.tobytes()


def start_capture_threads():
    """Launch one capture thread per lane (daemon threads)."""
    for lane_id in range(4):
        t = threading.Thread(target=capture_lane, args=(lane_id,), daemon=True)
        t.start()
        logger.info(f"Lane {lane_id}: capture thread launched.")


# ── Signal Overlay ────────────────────────────────────────────

def overlay_signal_info(frame, lane_id, count, signal, emergency):
    COLOR_MAP = {
        "GREEN":  (0, 210, 100),
        "YELLOW": (0, 210, 230),
        "RED":    (50, 50, 220),
    }
    color = COLOR_MAP.get(signal, (180, 180, 180))
    h, w  = frame.shape[:2]

    # Top-left badge
    cv2.rectangle(frame, (8, 8), (190, 72), (15, 20, 30), -1)
    cv2.rectangle(frame, (8, 8), (190, 72), color, 2)
    cv2.putText(frame, f"Lane {lane_id + 1}", (16, 32),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
    cv2.putText(frame, signal, (16, 62),
                cv2.FONT_HERSHEY_SIMPLEX, 0.85, color, 2)

    # Top-right vehicle count
    cv2.rectangle(frame, (w - 155, 8), (w - 8, 45), (15, 20, 30), -1)
    cv2.putText(frame, f"Vehicles: {count}", (w - 148, 33),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 210, 210), 2)

    # Emergency banner
    if emergency:
        cv2.rectangle(frame, (0, h - 42), (w, h), (0, 0, 170), -1)
        cv2.putText(frame, "EMERGENCY VEHICLE", (12, h - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2)

    return frame


# ── Routes ───────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def api_status():
    return jsonify({
        "lanes":        controller.get_all_lane_status(),
        "signals":      controller.get_signal_states(),
        "active_phase": controller.current_phase,
        "system_on":    system_running,
        "timestamp":    time.time(),
    })


@app.route("/api/start", methods=["POST"])
def api_start():
    global system_running
    if not system_running:
        system_running = True
        t = threading.Thread(target=traffic_management_loop, daemon=True)
        t.start()
        logger.info("Traffic management loop started.")
    return jsonify({"status": "started"})


@app.route("/api/stop", methods=["POST"])
def api_stop():
    global system_running
    system_running = False
    return jsonify({"status": "stopped"})


@app.route("/api/lane/<int:lane_id>/feed")
def lane_feed(lane_id: int):
    """MJPEG stream served from the pre-captured latest_frames buffer."""
    if lane_id not in range(4):
        return "Lane not found", 404
    return Response(
        mjpeg_generator(lane_id),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@app.route("/api/lane/<int:lane_id>/snapshot")
def lane_snapshot(lane_id: int):
    """Return a single JPEG snapshot (useful for debugging)."""
    with frame_locks[lane_id]:
        data = latest_frames[lane_id]
    if data is None:
        data = make_placeholder(lane_id)
    return Response(data, mimetype="image/jpeg")


@app.route("/api/stats")
def api_stats():
    return jsonify(controller.get_statistics())


@app.route("/api/emergency")
def api_emergency():
    return jsonify(emergency_detector.get_status())


# ── MJPEG Generator ───────────────────────────────────────────

def mjpeg_generator(lane_id: int):
    """
    Yield pre-captured JPEG frames as a multipart stream.
    Frames are buffered by the capture thread so this never blocks.
    """
    while True:
        with frame_locks[lane_id]:
            frame_data = latest_frames[lane_id]

        if frame_data is None:
            frame_data = make_placeholder(lane_id)
            time.sleep(0.1)
            continue

        yield (b"--frame\r\n"
               b"Content-Type: image/jpeg\r\n\r\n"
               + frame_data
               + b"\r\n")

        time.sleep(0.04)


# ── Traffic Management Loop ───────────────────────────────────

def traffic_management_loop():
    """
    Reads per-lane vehicle counts from the detector cache,
    updates the controller, and broadcasts via Socket.IO.
    """
    import random

    while system_running:
        lane_counts    = {}
        lane_emergency = {}

        for lane_id in range(4):
            count     = detector.get_latest_count(lane_id)
            emergency = detector.get_latest_emergency(lane_id)

            # Fallback simulation if detector has no data yet
            if count is None:
                count     = random.randint(0, 18)
                emergency = random.random() < 0.04

            lane_counts[lane_id]    = count
            lane_emergency[lane_id] = emergency

        emergency_detector.update(lane_emergency)
        controller.update(lane_counts, lane_emergency)

        status = {
            "lanes":        controller.get_all_lane_status(),
            "signals":      controller.get_signal_states(),
            "active_phase": controller.current_phase,
            "timestamp":    time.time(),
        }
        socketio.emit("traffic_update", status)
        time.sleep(1)


# ── WebSocket Events ─────────────────────────────────────────

@socketio.on("connect")
def on_connect():
    emit("traffic_update", {
        "lanes":        controller.get_all_lane_status(),
        "signals":      controller.get_signal_states(),
        "active_phase": controller.current_phase,
        "timestamp":    time.time(),
    })


# ── Entry Point ───────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("Starting Smart Traffic Management System...")

    # Start all 4 lane capture threads immediately
    start_capture_threads()

    # Small delay so threads can buffer their first frames
    time.sleep(2)

    # debug=False is important — debug=True causes double-init problems
    socketio.run(app, host="0.0.0.0", port=5000, debug=False)
