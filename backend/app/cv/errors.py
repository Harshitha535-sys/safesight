"""Explicit, typed errors so failures are reported honestly instead of hidden."""


class SafeSightError(Exception):
    code = "error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ModelNotFoundError(SafeSightError):
    code = "model_missing"


class ModelLoadError(SafeSightError):
    code = "model_load_failed"


class ModelDownloadError(SafeSightError):
    code = "model_download_failed"


class VideoOpenError(SafeSightError):
    code = "video_unreadable"


class ProcessingError(SafeSightError):
    code = "processing_failed"
