import logging
import threading
from dataclasses import dataclass

from app.core.config import settings

logger = logging.getLogger(__name__)

try:
    import serial
except ImportError:  # not available on machines without pyserial installed
    serial = None


@dataclass
class Telemetry:
    battery_voltage: float | None = None
    gps_lat: float | None = None
    gps_lon: float | None = None


class TelemetryUART:
    """Wrapper around pyserial for reading telemetry frames from the motor board.

    Set HARDWARE_MOCK=true (or pass mock=True) to use fake telemetry instead
    of a real serial port.
    """

    def __init__(self, port: str | None = None, baudrate: int | None = None, mock: bool | None = None):
        self.port = settings.uart_port if port is None else port
        self.baudrate = settings.uart_baudrate if baudrate is None else baudrate
        self.mock = settings.hardware_mock if mock is None else mock
        self._lock = threading.Lock()
        self._serial = None

        if not self.mock:
            if serial is None:
                raise RuntimeError("pyserial is not available; set HARDWARE_MOCK=true for local development")
            self._serial = serial.Serial(self.port, self.baudrate, timeout=0.5)

    def read_telemetry(self) -> Telemetry:
        """Reads and parses one telemetry frame; returns an empty Telemetry on timeout/error."""
        if self.mock:
            return Telemetry(battery_voltage=12.4, gps_lat=None, gps_lon=None)
        try:
            with self._lock:
                line = self._serial.readline()
            if not line:
                return Telemetry()
            # TODO: confirm the real UART frame format sent by the motor board firmware.
            return self._parse_frame(line)
        except Exception:
            logger.exception("Failed to read UART telemetry")
            return Telemetry()

    def close(self) -> None:
        if self._serial is not None:
            self._serial.close()

    def _parse_frame(self, line: bytes) -> Telemetry:
        # TODO: placeholder parser assuming "BAT:<volts>" ASCII frames until the real format is known.
        try:
            text = line.decode("ascii", errors="ignore").strip()
            if text.startswith("BAT:"):
                return Telemetry(battery_voltage=float(text.removeprefix("BAT:")))
        except Exception:
            logger.exception("Failed to parse UART frame: %r", line)
        return Telemetry()
