const statusEl = document.getElementById("conn-status");
const batteryEl = document.getElementById("battery");
const baitBtn = document.getElementById("bait-btn");
const updateBtn = document.getElementById("update-btn");
const updateResult = document.getElementById("update-result");
const backupList = document.getElementById("backup-list");

let ws = null;
let lastSentAt = 0;
const SEND_INTERVAL_MS = 100; // throttle joystick sends to ~10/sec

function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws/control`);

  ws.addEventListener("open", () => {
    statusEl.textContent = "Connected";
    statusEl.classList.remove("badge-off", "badge-error");
    statusEl.classList.add("badge-on");
  });

  ws.addEventListener("close", () => {
    statusEl.textContent = "Disconnected";
    statusEl.classList.remove("badge-on", "badge-error");
    statusEl.classList.add("badge-off");
    setTimeout(connect, 1000);
  });

  ws.addEventListener("message", (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type === "status") {
      batteryEl.textContent = `Battery: ${msg.battery != null ? msg.battery.toFixed(1) + "V" : "--"}`;
      if (msg.emergency_stopped) {
        statusEl.textContent = "EMERGENCY STOP";
        statusEl.classList.add("badge-error");
      }
    }
  });
}

function send(payload) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(payload));
  }
}

setInterval(() => send({ type: "heartbeat" }), 1000);

baitBtn.addEventListener("click", () => send({ type: "release_bait" }));

const joystick = nipplejs.create({
  zone: document.getElementById("joystick-zone"),
  mode: "static",
  position: { left: "50%", top: "50%" },
  color: "steelblue",
});

joystick.on("move", (evt, data) => {
  const now = Date.now();
  if (now - lastSentAt < SEND_INTERVAL_MS) return;
  lastSentAt = now;

  const distance = Math.min(data.distance, 75) / 75; // normalize 0..1
  const angleRad = data.angle.radian;
  const throttle = Math.round(Math.sin(angleRad) * distance * 100);
  const steering = Math.round(Math.cos(angleRad) * distance * 100);
  send({ type: "control", throttle, steering });
});

joystick.on("end", () => send({ type: "control", throttle: 0, steering: 0 }));

async function refreshBackups() {
  const res = await fetch("/backups");
  const data = await res.json();
  backupList.innerHTML = "";
  for (const name of data.backups) {
    const li = document.createElement("li");
    li.textContent = name + " ";
    const btn = document.createElement("button");
    btn.textContent = "Rollback";
    btn.addEventListener("click", async () => {
      if (!confirm(`Rollback to ${name}?`)) return;
      const r = await fetch(`/rollback/${encodeURIComponent(name)}`, { method: "POST" });
      updateResult.textContent = r.ok ? "Rollback OK" : "Rollback failed";
    });
    li.appendChild(btn);
    backupList.appendChild(li);
  }
}

updateBtn.addEventListener("click", async () => {
  updateResult.textContent = "Updating...";
  const res = await fetch("/update", { method: "POST" });
  updateResult.textContent = res.ok ? "Update OK" : "Update failed";
  refreshBackups();
});

connect();
refreshBackups();
