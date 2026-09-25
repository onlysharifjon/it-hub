"""Frontend shartnomasi: xato javobi `{ "message": "..." }`.

CRM'ning global xato formatiga tegmaslik uchun faqat shu istisno uchun handler o'rnatiladi.
"""
from fastapi import Request
from fastapi.responses import JSONResponse


class MinarError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


async def minar_error_handler(_: Request, exc: MinarError) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content={"message": exc.message})
