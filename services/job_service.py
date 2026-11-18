from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from queue import Queue
from uuid import uuid4

from repositories.job_repository import JobRepository
from services.errors import JobNotFoundError, PrinterNotFoundError, QueueFailedError
from services.file_service import FileService
from services.print_options import DEFAULT_PAPER_SIZE, normalize_paper_size
from services.printer_service import PrinterService


PAGE_RANGE_PATTERN = re.compile(r"^\d+(-\d+)?(,\d+(-\d+)?)*$")
ALLOWED_ORIENTATIONS = {"portrait", "landscape"}


def new_job_id() -> str:
    return f"job_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}"


class JobService:
    def __init__(self, repository: JobRepository, printer_service: PrinterService, file_service: FileService, job_queue: Queue[str]) -> None:
        self.repository = repository
        self.printer_service = printer_service
        self.file_service = file_service
        self.job_queue = job_queue

    def create_print_job(
        self,
        source_path: Path,
        printer_name: str,
        user_name: str | None,
        page_range: str | None = None,
        copies: str | int | None = None,
        paper_size: str | None = None,
        orientation: str | None = None,
    ) -> dict[str, object]:
        printer_name = (printer_name or "").strip()
        if not self.printer_service.printer_exists(printer_name):
            raise PrinterNotFoundError("打印机不存在或已断开")

        normalized_page_range = self._normalize_page_range(page_range)
        normalized_copies = self._normalize_copies(copies)
        normalized_paper_size = normalize_paper_size(paper_size)
        normalized_orientation = self._normalize_orientation(orientation)
        job_id = new_job_id()
        source_filename, stored_path, file_size_bytes = self.file_service.save_file(source_path, job_id)
        created_at = datetime.now(timezone.utc).isoformat()
        job = {
            "id": job_id,
            "user_id": None,
            "user_name": user_name.strip() if user_name else None,
            "source_filename": source_filename,
            "stored_filepath": str(stored_path),
            "file_size_bytes": file_size_bytes,
            "printer_name": printer_name,
            "page_range": normalized_page_range,
            "copies": normalized_copies,
            "paper_size": normalized_paper_size,
            "orientation": normalized_orientation,
            "status": "pending",
            "error_message": None,
            "created_at": created_at,
            "started_at": None,
            "finished_at": None,
            "cleaned_at": None,
        }
        self.repository.create_job(job)
        try:
            self.job_queue.put_nowait(job_id)
        except Exception as exc:
            raise QueueFailedError("打印任务入队失败") from exc
        return {"id": job_id, "status": "pending", "created_at": created_at}

    def get_job_detail(self, job_id: str) -> dict[str, object]:
        job = self.repository.get_job(job_id)
        if not job:
            raise JobNotFoundError("打印任务不存在")
        return self._to_response(job)

    def list_jobs(self, page_size: int = 10) -> list[dict[str, object]]:
        jobs, _ = self.repository.list_jobs(None, 1, page_size, "created_at", "desc")
        return [self._to_response(job) for job in jobs]

    def recover_startup_jobs(self, printing_mode: str) -> int:
        job_ids = self.repository.recover_startup_jobs(printing_mode)
        for job_id in job_ids:
            self.job_queue.put(job_id)
        return len(job_ids)

    def _to_response(self, job: dict[str, object]) -> dict[str, object]:
        return {
            "id": job["id"],
            "source_filename": job["source_filename"],
            "printer_name": job["printer_name"],
            "page_range": job.get("page_range"),
            "copies": job.get("copies", 1),
            "paper_size": job.get("paper_size", DEFAULT_PAPER_SIZE),
            "orientation": job.get("orientation", "portrait"),
            "status": job["status"],
            "error_message": job["error_message"],
            "created_at": job["created_at"],
        }

    def _normalize_page_range(self, page_range: str | None) -> str | None:
        value = (page_range or "").replace(" ", "").strip()
        if not value:
            return None
        if not PAGE_RANGE_PATTERN.match(value):
            raise ValueError("打印页面范围无效")
        for part in value.split(","):
            if "-" in part:
                start, end = part.split("-", 1)
                if int(start) < 1 or int(end) < int(start):
                    raise ValueError("打印页面范围无效")
        return value

    def _normalize_copies(self, copies: str | int | None) -> int:
        if copies in (None, ""):
            return 1
        try:
            value = int(copies)
        except (TypeError, ValueError) as exc:
            raise ValueError("打印份数无效") from exc
        if not 1 <= value <= 99:
            raise ValueError("打印份数应为 1-99")
        return value

    def _normalize_orientation(self, orientation: str | None) -> str:
        value = (orientation or "portrait").strip().lower()
        if value not in ALLOWED_ORIENTATIONS:
            raise ValueError("纸张方向无效")
        return value
