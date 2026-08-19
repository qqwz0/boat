import logging
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

UPDATER_SCRIPT = Path(__file__).resolve().parents[2] / "deploy" / "updater.py"


def _run_updater(args: list[str]) -> subprocess.CompletedProcess:
    """Runs deploy/updater.py as a subprocess so a failed update/rollback can't take the API process down with it."""
    return subprocess.run(
        [sys.executable, str(UPDATER_SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=300,
    )


@router.get("/health")
async def health(request: Request):
    """Used by deploy/updater.py to verify the app is up after a restart."""
    if not getattr(request.app.state, "ready", False):
        raise HTTPException(status_code=503, detail="not ready")
    return {"status": "ok"}


@router.get("/status")
async def status(request: Request):
    state = request.app.state.controller.state
    return {
        "connected": state.connected,
        "throttle": state.throttle,
        "steering": state.steering,
        "battery": state.battery_voltage,
        "emergency_stopped": state.emergency_stopped,
    }


@router.post("/update")
async def trigger_update():
    try:
        result = _run_updater(["update"])
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="update timed out")
    if result.returncode != 0:
        raise HTTPException(status_code=500, detail=result.stderr[-2000:] or result.stdout[-2000:])
    return {"status": "ok", "output": result.stdout[-4000:]}


@router.get("/backups")
async def list_backups():
    if not settings.backup_dir.exists():
        return {"backups": []}
    backups = sorted((p.name for p in settings.backup_dir.glob("backup_*.tar.gz")), reverse=True)
    return {"backups": backups}


@router.post("/rollback/{backup_id}")
async def rollback(backup_id: str):
    backup_path = settings.backup_dir / backup_id
    if not backup_path.exists():
        raise HTTPException(status_code=404, detail="backup not found")
    try:
        result = _run_updater(["rollback", backup_id])
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="rollback timed out")
    if result.returncode != 0:
        raise HTTPException(status_code=500, detail=result.stderr[-2000:] or result.stdout[-2000:])
    return {"status": "ok", "rolled_back_to": backup_id}
