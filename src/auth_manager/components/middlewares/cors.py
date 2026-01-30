from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

class CORSHandlingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = Response(status_code=200) if request.method == "OPTIONS" else await call_next(request)
        origin = request.headers.get("origin")
        response.headers["Access-Control-Allow-Origin"] = '*'
        response.headers["Access-Control-Allow-Methods"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        # response.headers["Access-Control-Allow-Credentials"] = "false"
        return response
