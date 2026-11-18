from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from queue import Queue

from config import Config, ensure_runtime_dirs
from repositories.job_repository import JobRepository
from services.cleanup_service import CleanupService
from services.file_service import FileService
from services.job_service import JobService
from services.printer_service import PrinterService
from workers.print_worker import PrintWorker


class DesktopRuntime:
    def __init__(self) -> None:
        self.config = Config()
        ensure_runtime_dirs(self.config)
        self._configure_logging()
        self.repository = JobRepository(self.config)
        self.repository.init_db()
        self.job_queue: Queue[str] = Queue()
        self.printer_service = PrinterService()
        self.file_service = FileService(self.config)
        self.job_service = JobService(self.repository, self.printer_service, self.file_service, self.job_queue)
        self.print_worker = PrintWorker(self.config, self.repository, self.job_queue)
        self.cleanup_service = CleanupService(self.config, self.repository)
        recovered_count = self.job_service.recover_startup_jobs(self.config.STARTUP_RECOVER_PRINTING_MODE)
        logging.getLogger(__name__).info("startup recovered_jobs=%s", recovered_count)
        self.print_worker.start()
        self.cleanup_service.start()

    def submit_file(self, source_path: Path, printer_name: str, user_name: str, page_range: str, copies: int, paper_size: str, orientation: str) -> dict[str, object]:
        return self.job_service.create_print_job(
            source_path=source_path,
            printer_name=printer_name,
            user_name=user_name,
            page_range=page_range,
            copies=copies,
            paper_size=paper_size,
            orientation=orientation,
        )

    def list_recent_jobs(self) -> list[dict[str, object]]:
        return self.job_service.list_jobs(10)

    def stop(self) -> None:
        self.cleanup_service.stop()
        self.print_worker.stop()

    def _configure_logging(self) -> None:
        handler = RotatingFileHandler(self.config.LOG_PATH, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        if not any(isinstance(existing, RotatingFileHandler) for existing in root_logger.handlers):
            root_logger.addHandler(handler)
