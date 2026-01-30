from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from src.auth_manager.components.enums.response_statuses import ResponseStatus
from src.auth_manager.components.exceptions.abstract import AbstractApplicationException
from src.auth_manager.dto.base.response import BaseResponseMeta, Message
from src.auth_manager.dto.error.http_exception import HttpExceptionResponse


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)

        except AbstractApplicationException as exc:
            meta = BaseResponseMeta(status=ResponseStatus.ERROR, code=exc.code, messages=[Message(name="error", content=str(exc))])
            return JSONResponse(
                status_code=int(exc.code),
                content=HttpExceptionResponse(payload={}, meta=meta).model_dump()
            )

        except Exception as exc:
            meta = BaseResponseMeta(status=ResponseStatus.ERROR, code="500", messages=[Message(name="error", content=str(exc))])
            return JSONResponse(
                status_code=500,
                content=HttpExceptionResponse(payload={},meta=meta).model_dump()
            )
