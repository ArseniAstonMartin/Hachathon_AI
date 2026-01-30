from logging import Handler, StreamHandler

from dependency_injector import containers, providers
from dependency_injector.providers import Singleton, Factory, List

from src.auth_manager.components.middlewares.cors import CORSHandlingMiddleware
from src.auth_manager.components.middlewares.error import ErrorHandlingMiddleware
from src.auth_manager.log import create_log_handler, get_logger
from src.auth_manager.components.database.relation.async_database import AsyncDatabaseRelational
from src.auth_manager.config import Settings
from src.auth_manager.routers.auth import AuthRouter
from src.auth_manager.routers.ping import PingRouter


class DependencyInjector(containers.DeclarativeContainer):
    settings = providers.Singleton(Settings)

    database = Factory(
        AsyncDatabaseRelational,
    )

    formatted_stream_handler: Handler = Factory(
        create_log_handler,
        handler=Factory(StreamHandler),
        name="FastAPI-Auth",
        level=settings.provided.app.log_level,
    )

    logger_handlers = List(
        formatted_stream_handler,
    )

    logger = Factory(
        get_logger,
        name=settings.provided.app.name,
        level=settings.provided.app.log_level,
        handlers=logger_handlers,
    )

    routers = List(
        Singleton(AuthRouter),
        Singleton(PingRouter)
    )

    middlewares = List(
        CORSHandlingMiddleware,
        ErrorHandlingMiddleware
    )