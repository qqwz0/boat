from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Set true on machines without the real motor board attached (dev laptops, CI).
    hardware_mock: bool = False

    # I2C: motor board control channel (throttle, steering, bait release).
    i2c_bus: int = 1
    i2c_address: int = 0x10  # TODO: confirm the real device address from the motor board's protocol docs.

    # UART: motor board telemetry (battery, GPS, ...).
    uart_port: str = "/dev/serial0"
    uart_baudrate: int = 9600

    # Failsafe: stop motors if no client heartbeat is received within this many seconds.
    failsafe_timeout_sec: float = 2.5

    # Web server
    web_host: str = "0.0.0.0"
    web_port: int = 8000

    # Self-update
    github_repo_url: str = ""
    update_branch: str = "main"
    max_backups: int = 5
    backup_dir: Path = Path("backups")

    # SQLite log of commands, events, and update history.
    db_path: Path = Path("boat.db")


settings = Settings()
