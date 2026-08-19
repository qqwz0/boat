import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter()

STATUS_BROADCAST_HZ = 10


@router.websocket("/ws/control")
async def ws_control(websocket: WebSocket):
    controller = websocket.app.state.controller
    await websocket.accept()
    controller.heartbeat()

    async def status_loop():
        while True:
            await asyncio.sleep(1 / STATUS_BROADCAST_HZ)
            state = controller.state
            await websocket.send_json(
                {
                    "type": "status",
                    "connected": state.connected,
                    "battery": state.battery_voltage,
                    "throttle": state.throttle,
                    "steering": state.steering,
                    "emergency_stopped": state.emergency_stopped,
                }
            )

    sender_task = asyncio.create_task(status_loop())
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("Ignoring non-JSON WS message: %r", raw)
                continue

            msg_type = message.get("type")
            if msg_type == "heartbeat":
                controller.heartbeat()
            elif msg_type == "control":
                controller.heartbeat()
                await controller.set_control(message.get("throttle", 0), message.get("steering", 0))
            elif msg_type == "release_bait":
                controller.heartbeat()
                await controller.release_bait()
            else:
                logger.warning("Unknown WS message type: %r", msg_type)
    except WebSocketDisconnect:
        logger.info("Control client disconnected")
    finally:
        sender_task.cancel()
        controller.mark_disconnected()
