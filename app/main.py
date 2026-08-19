import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import routes_admin, ws_control
from app.core.boat_controller import BoatController
from app.core.config import settings
from app.core.db import EventLog
from app.core.failsafe import FailsafeWatchdog
from app.hardware.i2c_driver import MotorBoardI2C
from app.hardware.uart_driver import TelemetryUART

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    event_log = EventLog(settings.db_path)
    i2c = MotorBoardI2C()
    uart = TelemetryUART()
    controller = BoatController(i2c=i2c, uart=uart, event_log=event_log)
    failsafe = FailsafeWatchdog(controller)

    app.state.controller = controller
    app.state.event_log = event_log
    app.state.ready = True

    failsafe.start()
    logger.info("Boat controller ready (HARDWARE_MOCK=%s)", settings.hardware_mock)
    try:
        yield
    finally:
        await failsafe.stop()
        i2c.close()
        uart.close()
        event_log.close()


app = FastAPI(title="Bait Boat Control", lifespan=lifespan)

app.include_router(ws_control.router)
app.include_router(routes_admin.router)

app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
