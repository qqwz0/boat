import asyncio
import logging
import time

from app.core.boat_controller import BoatController
from app.core.config import settings

logger = logging.getLogger(__name__)


class FailsafeWatchdog:
    """Background task that stops the motors if no heartbeat is received
    from the connected client within FAILSAFE_TIMEOUT_SEC.
    """

    def __init__(self, controller: BoatController, timeout_sec: float | None = None, check_interval: float = 0.5):
        self._controller = controller
        self._timeout_sec = settings.failsafe_timeout_sec if timeout_sec is None else timeout_sec
        self._check_interval = check_interval
        self._task: asyncio.Task | None = None
        self._stopped = False

    def start(self) -> None:
        self._stopped = False
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stopped = True
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run(self) -> None:
        while not self._stopped:
            await asyncio.sleep(self._check_interval)
            state = self._controller.state
            elapsed = time.monotonic() - state.last_heartbeat
            if state.connected and elapsed > self._timeout_sec:
                logger.warning("Heartbeat timeout (%.1fs) - triggering failsafe stop", elapsed)
                self._controller.mark_disconnected()
                await self._controller.emergency_stop()
