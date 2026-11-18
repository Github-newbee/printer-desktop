from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import uuid4

from config import Config
from services.errors import FileTooLargeError, InvalidFileTypeError, UploadFailedError


PDF_MAGIC = b"%PDF-"


class FileService:
    def __init__(self, config: Config) -> None:
        self.config = config

    def save_file(self, source_path: Path, job_id: str) -> tuple[str, Path, int]:
        source_path = source_path.expanduser()
        source_filename = source_path.name
        self._validate_extension(source_filename)
        if not source_path.is_file():
            raise UploadFailedError("找不到 PDF 文件")

        day_dir = self.config.UPLOAD_DIR / datetime.now().strftime("%Y-%m-%d")
        day_dir.mkdir(parents=True, exist_ok=True)
        stored_path = day_dir / f"{job_id}_{uuid4().hex[:8]}.pdf"
        total_size = 0
        try:
            with source_path.open("rb") as source, stored_path.open("wb") as target:
                header = source.read(len(PDF_MAGIC))
                if header != PDF_MAGIC:
                    raise InvalidFileTypeError("文件不是有效的 PDF")
                target.write(header)
                total_size = len(header)
                while chunk := source.read(1024 * 1024):
                    total_size += len(chunk)
                    if total_size > self.config.max_file_size_bytes:
                        raise FileTooLargeError(f"文件超过 {self.config.MAX_FILE_SIZE_MB} MB 限制")
                    target.write(chunk)
        except (InvalidFileTypeError, FileTooLargeError):
            stored_path.unlink(missing_ok=True)
            raise
        except OSError as exc:
            stored_path.unlink(missing_ok=True)
            raise UploadFailedError("保存 PDF 文件失败") from exc
        return source_filename, stored_path.resolve(), total_size

    def _validate_extension(self, filename: str) -> None:
        if Path(filename).suffix.lower() not in self.config.ALLOWED_EXTENSIONS:
            raise InvalidFileTypeError("仅支持 PDF 文件")
