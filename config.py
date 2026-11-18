from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


SOURCE_DIR = Path(__file__).resolve().parent
BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", SOURCE_DIR))
_DEFAULT_DATA_DIR = Path(os.getenv("LOCALAPPDATA", SOURCE_DIR / "data")) / "PrinterDesktop"


def _env_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    return default if raw_value is None else int(raw_value)


@dataclass(frozen=True)
class Config:
    DATA_DIR: Path = Path(os.getenv("PRINTER_DESKTOP_DATA_DIR", str(_DEFAULT_DATA_DIR)))
    DB_JOURNAL_MODE: str = os.getenv("DB_JOURNAL_MODE", "WAL")
    DB_BUSY_TIMEOUT_MS: int = _env_int("DB_BUSY_TIMEOUT_MS", 5000)
    MAX_FILE_SIZE_MB: int = _env_int("MAX_FILE_SIZE_MB", 50)
    ALLOWED_EXTENSIONS: tuple[str, ...] = (".pdf",)
    CLEANUP_SUCCESS_AFTER_MINUTES: int = _env_int("CLEANUP_SUCCESS_AFTER_MINUTES", 10)
    CLEANUP_FAILED_AFTER_HOURS: int = _env_int("CLEANUP_FAILED_AFTER_HOURS", 24)
    CLEANUP_INTERVAL_MINUTES: int = _env_int("CLEANUP_INTERVAL_MINUTES", 10)
    SUMATRA_PATH: Path = BUNDLE_DIR / "tools" / "SumatraPDF.exe"
    PRINT_COMMAND_TIMEOUT_SEC: int = _env_int("PRINT_COMMAND_TIMEOUT_SEC", 120)
    STARTUP_RECOVER_PRINTING_MODE: str = os.getenv("STARTUP_RECOVER_PRINTING_MODE", "fail")

    @property
    def DB_PATH(self) -> Path:
        return self.DATA_DIR / "data" / "print_service.db"

    @property
    def UPLOAD_DIR(self) -> Path:
        return self.DATA_DIR / "uploads"

    @property
    def LOG_PATH(self) -> Path:
        return self.DATA_DIR / "logs" / "app.log"

    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024


def ensure_runtime_dirs(config: Config) -> None:
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    config.LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
