from dependency_injector.wiring import Provide
from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, HTTPException, FastAPI
from fastapi.responses import JSONResponse

from src.auth_manager.components.database.redis.async_redis import AsyncRedisClient
from src.auth_manager.components.database.relation.async_database import AsyncDatabaseRelational
from src.auth_manager.components.injectable import injectable
from src.auth_manager.components.mixins.logger import LoggerMixin
from src.auth_manager.config import Settings
from src.auth_manager.routers.base import BaseRouter
from fastapi.middleware.cors import CORSMiddleware

@injectable()
class FastApiApp(LoggerMixin):
    def __init__(
        self,
        db: AsyncDatabaseRelational,
        redis: AsyncRedisClient,
        settings: Settings,
        routers: list[BaseRouter] = Provide["routers"],
        middlewares: list[BaseHTTPMiddleware] = Provide["middlewares"]
    ):
        self._db = db
        self._redis = redis
        self._app = FastAPI(title=settings.app.name, root_path=settings.app.root_path)

        self.__include_routers(routers)
        self.__add_middlewares(middlewares)
        self._app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @property
    def app(self) -> FastAPI:
        return self._app

    def __include_routers(self, routers: list[BaseRouter]):
        for router in routers:
            self._app.include_router(router.router, tags=[router.__class__.__name__])

    def __add_middlewares(self, middlewares: list[BaseHTTPMiddleware]):
        for middleware in middlewares:
            self._app.add_middleware(middleware)

    def __add_exception_handlers(self):
        @self._app.exception_handler(HTTPException)
        async def http_exception_handler(request: Request, exc: HTTPException):
            return JSONResponse({
                "payload": {},
                "meta": {
                    "status": "ERROR",
                    "code": f"{exc.status_code}",
                    "messages": [{"name": "Error", "content": exc.detail}]
                }
            }, exc.status_code)