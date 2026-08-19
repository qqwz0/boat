from unittest.mock import MagicMock

import pytest

from app.core.boat_controller import BoatController


@pytest.fixture
def controller():
    i2c = MagicMock()
    i2c.set_throttle.return_value = True
    i2c.set_steering.return_value = True
    i2c.release_bait.return_value = True
    uart = MagicMock()
    return BoatController(i2c=i2c, uart=uart)


@pytest.mark.asyncio
async def test_set_control_clamps_out_of_range_values(controller):
    await controller.set_control(throttle=500, steering=-500)
    assert controller.state.throttle == 100
    assert controller.state.steering == -100


@pytest.mark.asyncio
async def test_set_control_updates_state(controller):
    await controller.set_control(throttle=42, steering=-17)
    assert controller.state.throttle == 42
    assert controller.state.steering == -17


@pytest.mark.asyncio
async def test_emergency_stop_zeroes_controls_and_blocks_further_commands(controller):
    await controller.set_control(throttle=50, steering=50)
    await controller.emergency_stop()
    assert controller.state.throttle == 0
    assert controller.state.steering == 0
    assert controller.state.emergency_stopped is True

    await controller.set_control(throttle=80, steering=80)
    assert controller.state.throttle == 0  # command ignored while stopped


@pytest.mark.asyncio
async def test_reset_emergency_stop_allows_commands_again(controller):
    await controller.emergency_stop()
    controller.reset_emergency_stop()
    await controller.set_control(throttle=30, steering=10)
    assert controller.state.throttle == 30


def test_heartbeat_marks_connected(controller):
    controller.mark_disconnected()
    assert controller.state.connected is False
    controller.heartbeat()
    assert controller.state.connected is True
