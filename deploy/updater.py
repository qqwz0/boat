#!/usr/bin/env python3
"""Self-update logic for the bait boat control app.

Can be run standalone (via the boat-updater systemd timer or manually) or
invoked as a subprocess from app/api/routes_admin.py.

Usage:
    python updater.py update
    python updater.py rollback <backup_filename>
"""
import argparse
import logging
import subprocess
import sys
import tarfile
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = Path(__file__).resolve().parent / "updater.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()],
)
logger = logging.getLogger("updater")

sys.path.insert(0, str(PROJECT_ROOT))
from app.core.config import settings  # noqa: E402

SERVICE_NAME = "boat.service"
HEALTH_CHECK_RETRIES = 5
HEALTH_CHECK_DELAY_SEC = 2

EXCLUDE_DIRS = {".git", "venv", ".venv", "backups", "__pycache__"}


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    logger.info("Running: %s", " ".join(cmd))
    return subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, check=True)


def get_local_commit() -> str:
    return _run(["git", "rev-parse", "HEAD"]).stdout.strip()


def get_remote_commit(branch: str) -> str:
    _run(["git", "fetch", "origin", branch])
    return _run(["git", "rev-parse", f"origin/{branch}"]).stdout.strip()


def create_backup(commit_hash: str) -> Path:
    settings.backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    backup_path = settings.backup_dir / f"backup_{timestamp}_{commit_hash[:8]}.tar.gz"
    logger.info("Creating backup: %s", backup_path)

    def _filter(tarinfo: tarfile.TarInfo):
        parts = Path(tarinfo.name).parts
        if parts and parts[0] in EXCLUDE_DIRS:
            return None
        return tarinfo

    with tarfile.open(backup_path, "w:gz") as tar:
        tar.add(PROJECT_ROOT, arcname=".", filter=_filter)
    return backup_path


def prune_backups(max_backups: int) -> None:
    backups = sorted(settings.backup_dir.glob("backup_*.tar.gz"), key=lambda p: p.stat().st_mtime)
    while len(backups) > max_backups:
        oldest = backups.pop(0)
        logger.info("Pruning old backup: %s", oldest)
        oldest.unlink(missing_ok=True)


def pull_latest(branch: str) -> None:
    _run(["git", "pull", "origin", branch])


def requirements_changed(before: str, after: str) -> bool:
    diff = _run(["git", "diff", before, after, "--", "requirements.txt"]).stdout
    return bool(diff.strip())


def install_requirements() -> None:
    logger.info("Reinstalling requirements.txt")
    _run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "--break-system-packages"])


def restart_service() -> None:
    logger.info("Restarting %s", SERVICE_NAME)
    _run(["sudo", "systemctl", "restart", SERVICE_NAME])


def health_check() -> bool:
    import urllib.request

    url = f"http://localhost:{settings.web_port}/health"
    for attempt in range(1, HEALTH_CHECK_RETRIES + 1):
        time.sleep(HEALTH_CHECK_DELAY_SEC)
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                if resp.status == 200:
                    logger.info("Health check passed (attempt %d)", attempt)
                    return True
        except Exception as exc:
            logger.warning("Health check attempt %d failed: %s", attempt, exc)
    return False


def rollback_to_backup(backup_path: Path) -> None:
    logger.warning("Rolling back to %s", backup_path)
    with tarfile.open(backup_path, "r:gz") as tar:
        tar.extractall(PROJECT_ROOT)
    restart_service()


def run_update() -> int:
    branch = settings.update_branch
    local = get_local_commit()
    remote = get_remote_commit(branch)

    if local == remote:
        logger.info("Already up to date (%s)", local)
        return 0

    logger.info("New commit available: %s -> %s", local, remote)
    backup_path = create_backup(local)

    try:
        pull_latest(branch)
        if requirements_changed(local, remote):
            install_requirements()
        restart_service()

        if health_check():
            logger.info("Update to %s succeeded", remote)
            prune_backups(settings.max_backups)
            return 0

        logger.error("Health check failed after update - rolling back")
        rollback_to_backup(backup_path)
        return 1
    except subprocess.CalledProcessError as exc:
        logger.exception("Update step failed: %s", exc.stderr)
        rollback_to_backup(backup_path)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("update")
    rollback_parser = sub.add_parser("rollback")
    rollback_parser.add_argument("backup_name")

    args = parser.parse_args()
    if args.command == "update":
        return run_update()
    if args.command == "rollback":
        backup_path = settings.backup_dir / args.backup_name
        if not backup_path.exists():
            logger.error("Backup not found: %s", backup_path)
            return 1
        rollback_to_backup(backup_path)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
