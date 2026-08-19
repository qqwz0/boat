import logging
import threading
from dataclasses import dataclass

from app.core.config import settings

logger = logging.getLogger(__name__)

try:
    import smbus2
except ImportError:  # not available on non-Linux dev machines; mock mode covers that case
    smbus2 = None


# TODO: confirm the real register map / command byte layout against the motor board's protocol docs.
REG_THROTTLE = 0x01
REG_STEERING = 0x02
REG_RELEASE_BAIT = 0x03
REG_STATUS = 0x10


@dataclass
class MotorBoardStatus:
    ok: bool
    battery_voltage: float | None = None
    raw: bytes | None = None


class MotorBoardI2C:
    """Wrapper around smbus2 for the motor controller board.

    Set HARDWARE_MOCK=true (or pass mock=True) to use a fake in-memory
    implementation instead of talking to real hardware.
    """

    def __init__(self, bus: int | None = None, address: int | None = None, mock: bool | None = None):
        self.bus_num = settings.i2c_bus if bus is None else bus
        self.address = settings.i2c_address if address is None else address
        self.mock = settings.hardware_mock if mock is None else mock
        self._lock = threading.Lock()
        self._bus = None
        self._mock_state = {"throttle": 0, "steering": 0}

        if not self.mock:
            if smbus2 is None:
                raise RuntimeError("smbus2 is not available; set HARDWARE_MOCK=true for local development")
            self._bus = smbus2.SMBus(self.bus_num)

    def set_throttle(self, value: int) -> bool:
        """value: -100..100"""
        return self._write_register(REG_THROTTLE, value, "throttle")

    def set_steering(self, value: int) -> bool:
        """value: -100..100"""
        return self._write_register(REG_STEERING, value, "steering")

    def release_bait(self) -> bool:
        return self._write_register(REG_RELEASE_BAIT, 1, "release_bait")

    def read_status(self) -> MotorBoardStatus:
        """Reads back battery/status telemetry exposed over I2C by the motor board."""
        if self.mock:
            return MotorBoardStatus(ok=True, battery_voltage=12.4)
        try:
            with self._lock:
                raw = self._bus.read_i2c_block_data(self.address, REG_STATUS, 4)
            # TODO: confirm the actual status frame layout (battery voltage encoding, etc.).
            battery_voltage = raw[0] / 10.0
            return MotorBoardStatus(ok=True, battery_voltage=battery_voltage, raw=bytes(raw))
        except Exception:
            logger.exception("Failed to read I2C status from motor board")
            return MotorBoardStatus(ok=False)

    def close(self) -> None:
        if self._bus is not None:
            self._bus.close()

    def _write_register(self, register: int, value: int, label: str) -> bool:
        if self.mock:
            self._mock_state[label] = value
            logger.debug("MOCK I2C write %s=%s", label, value)
            return True
        try:
            with self._lock:
                self._bus.write_byte_data(self.address, register, value & 0xFF)
            return True
        except Exception:
            logger.exception("Failed to write I2C register for %s", label)
            return False
