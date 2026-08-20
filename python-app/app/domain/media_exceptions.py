from enum import Enum


class MediaProcessingCategory(str, Enum):
    NOT_CONFIGURED = "NOT_CONFIGURED"
    TELEGRAM_DOWNLOAD = "TELEGRAM_DOWNLOAD"
    INVALID_MEDIA = "INVALID_MEDIA"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    RATE_LIMITED = "RATE_LIMITED"
    PROVIDER_TEMPORARY = "PROVIDER_TEMPORARY"
    PROVIDER_RESPONSE = "PROVIDER_RESPONSE"


class MediaProcessingException(RuntimeError):
    def __init__(self, category: MediaProcessingCategory, message: str, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.category = category
        self.__cause__ = cause
