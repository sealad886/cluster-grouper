from typing import NoReturn

from fastapi import HTTPException


class IntegrationError(Exception):
    def __init__(self, code: str, message: str, status: int = 502) -> None:
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)


def fail(code: str, message: str, status: int = 400) -> NoReturn:
    raise HTTPException(status_code=status, detail={"code": code, "message": message})
