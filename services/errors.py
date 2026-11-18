from __future__ import annotations


class ServiceError(Exception):
    code = "SERVICE_ERROR"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.code)
        self.message = message or self.code


class InvalidFileTypeError(ServiceError):
    code = "INVALID_FILE_TYPE"


class FileTooLargeError(ServiceError):
    code = "FILE_TOO_LARGE"


class PrinterNotFoundError(ServiceError):
    code = "PRINTER_NOT_FOUND"


class UploadFailedError(ServiceError):
    code = "UPLOAD_FAILED"


class QueueFailedError(ServiceError):
    code = "QUEUE_FAILED"


class JobNotFoundError(ServiceError):
    code = "JOB_NOT_FOUND"
