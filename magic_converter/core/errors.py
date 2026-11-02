"""Exceptions carrying a short user-facing message plus optional technical detail."""


class ConversionError(Exception):
    def __init__(self, message: str, detail: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail


class ConversionCancelled(Exception):
    pass
