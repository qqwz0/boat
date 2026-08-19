import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Callable

from app.core.db import EventLog
from app.hardware.i2c_driver import MotorBoardI2C
from app.hardware.uart_driver import TelemetryUART

logger = logging.getLogger(__name__)

THROTTLE_MIN, THROTTLE_MAX = -100, 100
STEERING_MIN, STEERING_MAX = -100, 100


@dataclass
class BoatState:
    throttle: int = 0
    steering: int = 0
    battery_voltage: float | None = None
    connected: bool = False
    last_heartbeat: float = field(default_factory=time.monotonic)
    emergency_stopped: bool = False


class BoatController:
    """Central state machine for the boat.

    Validates incoming commands, drives the hardware layer off the event loop
    via asyncio.to_thread, tracks state, and notifies subscribers so it can be
    broadcast back to WebSocket clients.
    """

    def __init__(self, i2c: MotorBoardI2C, uart: TelemetryUART, event_log: EventLog | None = None):
        self._i2c = i2c
        self._uart = uart
        self._event_log = event_log
        self._state = BoatState()
        self._lock = asyncio.Lock()
        self._subscribers: list[Callable[[BoatState], None]] = []

    @property
    def state(self) -> BoatState:
        return self._state

    def subscribe(self, callback: Callable[[BoatState], None]) -> None:
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[BoatState], None]) -> None:
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    async def set_control(self, throttle: int, steering: int) -> None:
        """Clamps and applies a throttle/steering command; ignored while emergency-stopped."""
        throttle = max(THROTTLE_MIN, min(THROTTLE_MAX, int(throttle)))
        steering = max(STEERING_MIN, min(STEERING_MAX, int(steering)))
        async with self._lock:
            if self._state.emergency_stopped:
                return
            ok_throttle = await asyncio.to_thread(self._i2c.set_throttle, throttle)
            ok_steering = await asyncio.to_thread(self._i2c.set_steering, steering)
            if ok_throttle and ok_steering:
                self._state.throttle = throttle
                self._state.steering = steering
        self._log_event("control", f"throttle={throttle} steering={steering}")
        self._notify()

    async def release_bait(self) -> None:
        async with self._lock:
            if self._state.emergency_stopped:
                return
            await asyncio.to_thread(self._i2c.release_bait)
        self._log_event("release_bait", "")
        self._notify()

    async def emergency_stop(self) -> None:
        """Zeroes throttle/steering and latches the boat in a stopped state until reset."""
        async with self._lock:
            self._state.emergency_stopped = True
            self._state.throttle = 0
            self._state.steering = 0
            await asyncio.to_thread(self._i2c.set_throttle, 0)
            await asyncio.to_thread(self._i2c.set_steering, 0)
        logger.warning("Emergency stop triggered")
        self._log_event("emergency_stop", "")
        self._notify()

    def reset_emergency_stop(self) -> None:
        self._state.emergency_stopped = False
        self._notify()

    def heartbeat(self) -> None:
        self._state.last_heartbeat = time.monotonic()
        self._state.connected = True

    def mark_disconnected(self) -> None:
        self._state.connected = False

    async def refresh_telemetry(self) -> None:
        telemetry = await asyncio.to_thread(self._uart.read_telemetry)
        if telemetry.battery_voltage is not None:
            self._state.battery_voltage = telemetry.battery_voltage
        self._notify()

    def _notify(self) -> None:
        for callback in list(self._subscribers):
            try:
                callback(self._state)
            except Exception:
                logger.exception("Subscriber callback failed")

    def _log_event(self, event_type: str, detail: str) -> None:
        if self._event_log is not None:
            try:
                self._event_log.log_event(event_type, detail)
            except Exception:
                logger.exception("Failed to log event")
