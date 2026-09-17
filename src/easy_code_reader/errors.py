"""Errors shared by repository, source and decompiler services."""


class ReaderError(Exception):
    def __init__(self, code: str, message: str, hint: str = ""):
        super().__init__(message)
        self.code = code
        self.hint = hint

    def as_dict(self) -> dict:
        return {"error": {"code": self.code, "message": str(self), "hint": self.hint}}
