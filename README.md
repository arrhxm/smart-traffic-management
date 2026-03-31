# 🚦 Smart AI-Based Traffic Management System

A real-time, AI-driven traffic signal control system using **YOLOv8** and **Computer Vision** to dynamically adjust signal timings based on live vehicle density.

---

## 📁 Project Structure

```
traffic_system/
├── app.py                      # Flask application entry point
├── demo.py                     # Standalone demo (no camera needed)
├── requirements.txt
│
├── utils/
│   ├── vehicle_detector.py     # YOLOv8 vehicle detection
│   ├── traffic_controller.py   # Adaptive signal timing engine
│   ├── emergency_detector.py   # Emergency vehicle alert manager
│   └── logger.py               # Centralised logging
│
├── models/
│   └── yolov8n.pt              # YOLOv8 nano weights (auto-downloaded)
│
├── templates/
│   └── index.html              # Dashboard HTML
│
├── static/
│   ├── css/style.css           # Dashboard styles
│   ├── js/dashboard.js         # Real-time Socket.IO + Chart.js frontend
│   └── img/no-feed.png         # Fallback image
│
├── test_videos/                # Put sample .mp4 lane videos here
│   ├── lane1.mp4
│   ├── lane2.mp4
│   ├── lane3.mp4
│   └── lane4.mp4
│
└── logs/                       # Auto-created log files
```

---

## ⚙️ Setup & Installation

### 1. Clone / Download

```bash
git clone https://github.com/yourname/smart-traffic-system.git
cd smart-traffic-system/traffic_system
```

### 2. Create Virtual Environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

> YOLOv8 weights (`yolov8n.pt`) are downloaded automatically on first run.

### 4. Add Test Videos *(optional)*

Place `.mp4` video files of traffic intersections in `test_videos/`:
- `lane1.mp4`, `lane2.mp4`, `lane3.mp4`, `lane4.mp4`

If videos are missing, the system runs in **demo mode** with simulated counts.

---

## 🚀 Running the System

### Option A — Full Web Dashboard

```bash
python app.py
```

Open your browser at: **http://localhost:5000**

Use the **▶ Start** button to begin real-time monitoring.

### Option B — Terminal Demo (no camera needed)

```bash
python demo.py
```

---

## 🎯 How It Works

```
Camera Feed (MP4 / RTSP / Webcam)
        │
        ▼
 VehicleDetector (YOLOv8)
        │  detects & counts vehicles per lane
        │  flags emergency vehicles
        ▼
 TrafficController
        │  computes green time = MIN + density × (MAX - MIN)
        │  emergency lane jumps to front of queue
        │  YELLOW phase separates every GREEN → RED transition
        ▼
 Flask + Socket.IO
        │  pushes live updates to all connected browsers
        ▼
 Dashboard (Chart.js)
        │  lane cards, density bars, signal badges, event log
        └─ live camera streams via MJPEG
```

---

## 🧠 Adaptive Signal Algorithm

| Variable | Value |
|---|---|
| Minimum green time | 10 seconds |
| Maximum green time | 60 seconds |
| Yellow phase | 3 seconds (fixed) |
| Emergency green | 20 seconds (forced) |

**Formula:**

```
green_time = MIN_GREEN + density × (MAX_GREEN - MIN_GREEN)
```

Where `density = avg_vehicle_count / 30` (clamped to 0–1).

---

## 🔌 API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET`  | `/` | Dashboard UI |
| `GET`  | `/api/status` | Current signal & density state |
| `POST` | `/api/start` | Start the management loop |
| `POST` | `/api/stop` | Stop the management loop |
| `GET`  | `/api/lane/<id>/feed` | MJPEG video stream for lane `id` |
| `GET`  | `/api/stats` | Historical statistics |
| `GET`  | `/api/emergency` | Emergency detection status |

---

## 🔮 Future Scope

- [ ] GPS-based emergency vehicle pre-clearing
- [ ] AI traffic prediction (LSTM / time-series)
- [ ] RTSP camera stream support
- [ ] Cloud deployment (AWS / GCP)
- [ ] Integration with smart city APIs
- [ ] Mobile alert notifications

---

## 📦 Tech Stack

| Layer | Technology |
|---|---|
| Object Detection | YOLOv8 (Ultralytics) |
| Computer Vision | OpenCV |
| Backend | Python 3.11, Flask, Flask-SocketIO |
| Frontend | HTML5, CSS3, JavaScript |
| Charts | Chart.js |
| Real-time | Socket.IO (WebSockets) |
| Data | NumPy, Pandas |

---

## 👨‍💻 License

MIT License — free for academic and personal use.
