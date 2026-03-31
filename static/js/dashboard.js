// ============================================================
//  static/js/dashboard.js  — Fixed with staggered feed loading
// ============================================================

"use strict";

// ── Socket.IO ────────────────────────────────────────────────
const socket    = io({ transports: ["websocket", "polling"] });
const connDot   = document.getElementById("conn-dot");
const connLabel = document.getElementById("conn-label");

socket.on("connect", () => {
  connDot.className   = "status-dot connected";
  connLabel.textContent = "Connected";
  logEvent("System", "Connected to server.");
});

socket.on("disconnect", () => {
  connDot.className   = "status-dot disconnected";
  connLabel.textContent = "Disconnected";
  logEvent("System", "Disconnected from server.");
});

socket.on("traffic_update", (data) => {
  updateLaneCards(data.lanes);
  updateSummary(data);
  updateCharts(data.lanes);
  updateEmergencyBanner(data.lanes);
  updateFeedBadges(data.signals);
});

// ── Lane Cards ───────────────────────────────────────────────
const lanesGrid = document.getElementById("lanes-grid");

function updateLaneCards(lanes) {
  lanes.forEach((lane) => {
    let card = document.getElementById(`lane-card-${lane.lane_id}`);
    if (!card) {
      card = createLaneCard(lane.lane_id);
      lanesGrid.appendChild(card);
    }
    renderLaneCard(card, lane);
  });
}

function createLaneCard(id) {
  const card = document.createElement("div");
  card.className = "lane-card";
  card.id = `lane-card-${id}`;
  card.innerHTML = `
    <div class="lane-card__header">
      <span class="lane-card__title">Lane ${id + 1}</span>
      <div style="display:flex;gap:0.4rem;align-items:center">
        <span class="emergency-tag hidden" id="em-tag-${id}">🚨 EMERGENCY</span>
        <span class="signal-badge RED" id="signal-badge-${id}">RED</span>
      </div>
    </div>
    <div class="timer-ring" id="timer-${id}">—</div>
    <div class="lane-card__stat">
      <span class="lane-card__stat-label">Vehicles</span>
      <span class="lane-card__stat-val" id="count-${id}">0</span>
    </div>
    <div class="lane-card__stat">
      <span class="lane-card__stat-label">Density</span>
      <span class="lane-card__stat-val" id="density-${id}">0%</span>
    </div>
    <div class="lane-card__stat">
      <span class="lane-card__stat-label">Green Time</span>
      <span class="lane-card__stat-val" id="green-time-${id}">-- s</span>
    </div>
    <div class="lane-card__stat">
      <span class="lane-card__stat-label">Wait Time</span>
      <span class="lane-card__stat-val" id="wait-${id}">0 s</span>
    </div>
    <div class="density-bar">
      <div class="density-bar__fill" id="density-bar-${id}" style="width:0%"></div>
    </div>`;
  return card;
}

function renderLaneCard(card, lane) {
  const sig = lane.signal;
  card.className = `lane-card signal-${sig.toLowerCase()}${lane.has_emergency ? " emergency" : ""}`;

  const badge = document.getElementById(`signal-badge-${lane.lane_id}`);
  badge.textContent = sig;
  badge.className   = `signal-badge ${sig}`;

  document.getElementById(`em-tag-${lane.lane_id}`)
          .classList.toggle("hidden", !lane.has_emergency);

  const timerEl = document.getElementById(`timer-${lane.lane_id}`);
  timerEl.textContent = (sig === "GREEN" || sig === "YELLOW")
    ? `${lane.time_remaining}s` : "—";
  timerEl.style.color = sig === "GREEN" ? "var(--teal)"
                       : sig === "YELLOW" ? "var(--amber)" : "var(--muted)";

  document.getElementById(`count-${lane.lane_id}`).textContent     = lane.vehicle_count;
  document.getElementById(`density-${lane.lane_id}`).textContent   = `${lane.density_pct}%`;
  document.getElementById(`green-time-${lane.lane_id}`).textContent = `${lane.green_time} s`;
  document.getElementById(`wait-${lane.lane_id}`).textContent       = `${lane.wait_time} s`;

  const bar = document.getElementById(`density-bar-${lane.lane_id}`);
  bar.style.width = `${lane.density_pct}%`;
  bar.className   = "density-bar__fill"
    + (lane.density_pct > 70 ? " high" : lane.density_pct > 40 ? " medium" : "");
}

// ── Summary ───────────────────────────────────────────────────
function updateSummary(data) {
  document.getElementById("total-vehicles").textContent =
    data.lanes.reduce((s, l) => s + l.vehicle_count, 0);
  document.getElementById("active-phase").textContent =
    `Lane ${data.active_phase + 1}`;
  document.getElementById("avg-density").textContent =
    (data.lanes.reduce((s, l) => s + l.density_pct, 0) / data.lanes.length).toFixed(1) + "%";
  document.getElementById("emergency-count").textContent =
    data.lanes.filter(l => l.has_emergency).length;
}

// ── Emergency Banner ──────────────────────────────────────────
function updateEmergencyBanner(lanes) {
  const banner  = document.getElementById("emergency-banner");
  const emLanes = lanes.filter(l => l.has_emergency);
  if (emLanes.length > 0) {
    banner.classList.remove("hidden");
    document.getElementById("emergency-lane-text").textContent =
      emLanes.map(l => `Lane ${l.lane_id + 1}`).join(", ");
  } else {
    banner.classList.add("hidden");
  }
}

// ── Feed Signal Badges ────────────────────────────────────────
function updateFeedBadges(signals) {
  Object.entries(signals).forEach(([id, sig]) => {
    const b = document.getElementById(`feed-signal-${id}`);
    if (b) { b.textContent = sig; b.className = `signal-badge ${sig}`; }
  });
}

// ── Charts ────────────────────────────────────────────────────
const LANE_COLORS = ["#00c9a7", "#f4a261", "#e63946", "#7a9bbe"];
let densityChart, timingChart;

function initCharts() {
  const base = {
    responsive: true,
    animation:  { duration: 350 },
    plugins: { legend: { display: false } },
    scales: {
      x: { ticks: { color: "#7a9bbe" }, grid: { color: "rgba(255,255,255,0.05)" } },
      y: { ticks: { color: "#7a9bbe" }, grid: { color: "rgba(255,255,255,0.08)" }, beginAtZero: true },
    },
  };

  const labels = ["Lane 1", "Lane 2", "Lane 3", "Lane 4"];

  densityChart = new Chart(document.getElementById("density-chart"), {
    type: "bar",
    data: {
      labels,
      datasets: [{ data: [0,0,0,0],
        backgroundColor: LANE_COLORS.map(c => c + "bb"),
        borderColor: LANE_COLORS, borderWidth: 2, borderRadius: 6 }],
    },
    options: { ...base, scales: { ...base.scales,
      y: { ...base.scales.y, max: 100 } } },
  });

  timingChart = new Chart(document.getElementById("timing-chart"), {
    type: "bar",
    data: {
      labels,
      datasets: [{ data: [0,0,0,0],
        backgroundColor: LANE_COLORS.map(c => c + "99"),
        borderColor: LANE_COLORS, borderWidth: 2, borderRadius: 6 }],
    },
    options: { ...base, scales: { ...base.scales,
      y: { ...base.scales.y, max: 60 } } },
  });
}

function updateCharts(lanes) {
  if (!densityChart || !timingChart) return;
  densityChart.data.datasets[0].data = lanes.map(l => l.density_pct);
  timingChart.data.datasets[0].data  = lanes.map(l => l.green_time);
  densityChart.update("none");
  timingChart.update("none");
}

// ── Event Log ─────────────────────────────────────────────────
let firstLog = true;
function logEvent(src, msg, emergency = false) {
  const log = document.getElementById("event-log");
  if (firstLog) { log.innerHTML = ""; firstLog = false; }

  const t    = new Date().toTimeString().slice(0, 8);
  const item = document.createElement("div");
  item.className = `event-log__item${emergency ? " emergency" : ""}`;
  item.innerHTML =
    `<span class="event-log__time">${t}</span>` +
    `<span class="event-log__msg">[${src}] ${msg}</span>`;
  log.insertBefore(item, log.firstChild);
  while (log.children.length > 60) log.removeChild(log.lastChild);
}

// ── System Controls ───────────────────────────────────────────
async function startSystem() {
  const r = await fetch("/api/start", { method: "POST" });
  const d = await r.json();
  logEvent("System", `Started — ${d.status}`);
}
async function stopSystem() {
  const r = await fetch("/api/stop", { method: "POST" });
  const d = await r.json();
  logEvent("System", `Stopped — ${d.status}`);
}

// ── Staggered Feed Loading ────────────────────────────────────
// Load each lane feed with a delay so all 4 appear without blocking the page.
function buildFeedCard(laneId) {
  const card = document.createElement("div");
  card.className = "feed-card";
  card.innerHTML = `
    <div class="feed-card__header">
      <span>Lane ${laneId + 1}</span>
      <span class="signal-badge RED" id="feed-signal-${laneId}">RED</span>
    </div>
    <div class="feed-loading" id="feed-loading-${laneId}">Loading feed...</div>
    <img
      class="feed-card__img hidden"
      id="feed-img-${laneId}"
      alt="Lane ${laneId + 1}"
      onload="onFeedLoaded(${laneId})"
      onerror="onFeedError(${laneId})"
    />`;
  return card;
}

function onFeedLoaded(laneId) {
  document.getElementById(`feed-loading-${laneId}`).style.display = "none";
  document.getElementById(`feed-img-${laneId}`).classList.remove("hidden");
  document.getElementById("feeds-hint").textContent = "";
}

function onFeedError(laneId) {
  document.getElementById(`feed-loading-${laneId}`).textContent = "Feed unavailable";
  logEvent("Feed", `Lane ${laneId + 1} feed error.`);
}

function loadFeeds() {
  const grid = document.getElementById("feeds-grid");
  for (let i = 0; i < 4; i++) {
    const card = buildFeedCard(i);
    grid.appendChild(card);

    // Stagger: each lane starts loading 600ms after the previous
    setTimeout(() => {
      const img = document.getElementById(`feed-img-${i}`);
      img.src   = `/api/lane/${i}/feed`;
    }, i * 600);
  }
}

// ── Init ──────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  initCharts();
  // Wait 1.5s after page load before starting feeds
  // (gives the server time to buffer the first frames)
  setTimeout(loadFeeds, 1500);
  logEvent("System", "Dashboard ready.");
});
