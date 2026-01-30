from abc import ABC, abstractmethod
from types import FunctionType

from dependency_injector.wiring import inject, Provide
from fastapi import APIRouter, FastAPI, status

from src.auth_manager.components.enums.http_methods import HTTPMethod
from src.auth_manager.components.injectable import injectable
from src.auth_manager.components.mixins.logger import LoggerMixin
from src.auth_manager.config import UrlSettings


@injectable()
class BaseRouter(ABC, LoggerMixin):
    _router: APIRouter

    @inject
    def __init__(
        self,
        router: APIRouter | None = None,
        urls: UrlSettings = Provide["settings.provided.url"],
    ):
        self._router = router or APIRouter()
        self._urls = urls
        self.__initialize()

    def init_handler(
            self,
            handler: FunctionType,
            method: HTTPMethod,
            url: str,
            status_code: int = status.HTTP_200_OK,
    ):
        """
        Инициализирует обработчик маршрута FastAPI.

        :param method: HTTP-метод из перечисления HTTPMethod
        :param url: путь маршрута
        :param handler: функция-обработчик
        """

        route_func = {
            HTTPMethod.GET: self._router.get,
            HTTPMethod.POST: self._router.post,
            HTTPMethod.PUT: self._router.put,
            HTTPMethod.DELETE: self._router.delete,
            HTTPMethod.PATCH: self._router.patch,
        }.get(method)

        route_func(url,
                   status_code=status_code
                   )(handler)
        self._logger.info(f"Handler '{handler.__name__}' initialized on [{method.upper()}] {url}")

    def __initialize(self):
        self._init_routes()
        self._logger.info(f"Router {self.__class__.__name__} initialized")

    @abstractmethod
    def _init_routes(self):
        """
        Привязка эндпоинтов FastAPI к роутеру.
        """
        pass

    @property
    def router(self) -> APIRouter:
        return self._router

    def include_in(self, app: FastAPI):
        """
        Включает роутер в FastAPI приложение.
        """
        app.include_router(self._router)