# Bait Boat

Control system for a Raspberry Pi 3+ powered bait boat: a phone connects over
a local Wi-Fi network and drives the boat (throttle, steering, bait release)
from a browser in real time, with an automatic failsafe stop on lost
connection and a self-updating deployment with backup/rollback.

## Hardware

- Raspberry Pi 3+ running Raspberry Pi OS Lite, configured as a Wi-Fi access
  point (hostapd + dnsmasq) so a phone can connect directly without internet.
- A separate motor-controller board, driven over **I2C** (throttle, steering,
  bait release) and reporting telemetry (battery, GPS, ...) over **UART**.
- The exact I2C register map/address and UART frame format are **not yet
  known** and must be confirmed against the motor board's own documentation.
  See the `TODO` comments in `app/hardware/i2c_driver.py` and
  `app/hardware/uart_driver.py` — those are the only two files that need real
  protocol details before this runs against real hardware.

## Stack

Python 3.11+, FastAPI + Uvicorn, WebSocket for real-time control, `smbus2`
for I2C, `pyserial` for UART (blocking hardware calls run via
`asyncio.to_thread` so they never block the event loop), `pydantic-settings`
for `.env` config, SQLite for command/event/update history, vanilla
HTML/CSS/JS with `nipplejs` (CDN) for the joystick, and systemd for process
management and the hourly self-update timer.

## Local development (no hardware attached)

```bash
python -m venv .venv
.venv/Scripts/activate   # or: source .venv/bin/activate on Linux/macOS
pip install -r requirements.txt
cp .env.example .env     # HARDWARE_MOCK=true by default
uvicorn app.main:app --reload
```

Open `http://localhost:8000` — the hardware drivers run in mock mode
(`HARDWARE_MOCK=true`), returning fake telemetry and no-op-ing hardware
writes, so the full UI and control flow work without a Pi or motor board.

Run the tests (they mock the hardware drivers, no real I2C/UART needed):

```bash
pytest
```

## Deploying to a Raspberry Pi

1. Clone this repo onto the Pi (e.g. `/home/pi/Boat`).
2. Create a venv and install dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env`, set `HARDWARE_MOCK=false`, and fill in the
   real `I2C_BUS`/`I2C_ADDRESS`/`UART_PORT`/`UART_BAUDRATE` and
   `GITHUB_REPO_URL` values.
4. Wire up the motor board's I2C and UART lines to the Pi's GPIO header,
   confirm the bus/address/port match your `.env`, and enable I2C/UART via
   `raspi-config` if not already on.
5. Install the systemd units:
   ```bash
   sudo deploy/install.sh
   ```
   This installs and enables `boat.service` (the app, `Restart=always`) and
   `boat-updater.timer` (runs `deploy/updater.py update` hourly). It prints
   follow-up steps for adjusting paths/user in the unit files and for
   granting the updater passwordless `sudo` to restart `boat.service`.

## Updating and rollback

- **Automatic**: the `boat-updater` timer runs hourly. If the remote branch
  has a new commit, it backs up the current tree to `backups/`, pulls,
  reinstalls `requirements.txt` if it changed, restarts `boat.service`, and
  health-checks `/health`. If the health check fails, it automatically
  unpacks the last backup and restarts again.
- **Manual, via the admin UI**: the "Адміністрування" panel on the control
  page has an update button and a list of backups, each with a rollback
  button (calls `POST /update` / `POST /rollback/{backup_id}`).
- **Manual, via CLI**: `python deploy/updater.py update` or
  `python deploy/updater.py rollback <backup_filename>`.
- Backups are kept up to `MAX_BACKUPS` (default 5); older ones are pruned
  automatically after a successful update.
