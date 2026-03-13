from logging import Handler, StreamHandler

from dependency_injector import containers, providers
from dependency_injector.providers import Factory, List

from src.auth_manager.components.database.redis.async_redis import AsyncRedisClient
from src.auth_manager.components.database.relation.async_database import AsyncDatabaseRelational
from src.auth_manager.components.fast_api_app import FastApiApp
from src.auth_manager.components.middlewares.cors import CORSHandlingMiddleware
from src.auth_manager.components.middlewares.error import ErrorHandlingMiddleware
from src.auth_manager.components.storage.s3 import S3ObjectStorage
from src.auth_manager.config import load_settings
from src.auth_manager.domains.bot.router import BotRouter
from src.auth_manager.domains.bot.integration import (
    TelegramBackendGateway,
    TelegramBotApiClient,
    TelegramEventLog,
    TelegramUpdateProcessor,
)
from src.auth_manager.domains.bot.security import TelegramPrincipalResolver
from src.auth_manager.domains.bot.services import BotDialogStateStore, TelegramBotService
from src.auth_manager.domains.compliance.router import ComplianceRouter
from src.auth_manager.domains.compliance.services import ComplianceSourceService, PravoBySourceClient
from src.auth_manager.domains.diff.router import DiffRouter
from src.auth_manager.domains.diff.services import ComparisonJobQueue, ComparisonJobService
from src.auth_manager.domains.health.router import HealthRouter
from src.auth_manager.domains.ingestion.router import IngestionRouter
from src.auth_manager.domains.ingestion.services import DocumentIngestionService
from src.auth_manager.domains.report.router import ReportRouter
from src.auth_manager.domains.tenancy.router import TenancyRouter
from src.auth_manager.log import create_log_handler, get_logger
from src.auth_manager.routers.auth import AuthRouter
from src.auth_manager.routers.ping import PingRouter
from src.auth_manager.runtime.api import ApiRuntime
from src.auth_manager.runtime.bot import BotRuntime
from src.auth_manager.runtime.worker import WorkerRuntime


class DependencyInjector(containers.DeclarativeContainer):
    settings = providers.Singleton(load_settings)

    database = providers.Singleton(
        AsyncDatabaseRelational,
    )

    async_redis_client = providers.Singleton(
        AsyncRedisClient,
    )

    object_storage = providers.Singleton(
        S3ObjectStorage,
    )

    formatted_stream_handler: Handler = Factory(
        create_log_handler,
        handler=Factory(StreamHandler),
        name="FastAPI-Monolith",
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

    comparison_job_queue = providers.Singleton(
        ComparisonJobQueue,
        redis=async_redis_client,
        worker_settings=settings.provided.worker,
    )

    comparison_job_service = providers.Singleton(
        ComparisonJobService,
        db=database,
        queue=comparison_job_queue,
    )

    bot_dialog_state_store = providers.Singleton(
        BotDialogStateStore,
    )

    telegram_bot_service = providers.Singleton(
        TelegramBotService,
        dialog_state_store=bot_dialog_state_store,
    )

    telegram_event_log = providers.Singleton(
        TelegramEventLog,
    )

    telegram_principal_resolver = providers.Singleton(
        TelegramPrincipalResolver,
        settings=settings,
        db=database,
    )

    document_ingestion_service = providers.Singleton(
        DocumentIngestionService,
        db=database,
        object_storage=object_storage,
    )

    telegram_bot_api_client = providers.Singleton(
        TelegramBotApiClient,
        settings=settings,
    )

    telegram_update_processor = providers.Singleton(
        TelegramUpdateProcessor,
        settings=settings,
        telegram_bot_service=telegram_bot_service,
        telegram_event_log=telegram_event_log,
        telegram_principal_resolver=telegram_principal_resolver,
        telegram_bot_api_client=telegram_bot_api_client,
        document_ingestion_service=document_ingestion_service,
    )

    telegram_backend_gateway = providers.Singleton(
        TelegramBackendGateway,
        settings=settings,
    )

    pravo_by_source_client = providers.Singleton(
        PravoBySourceClient,
        settings=settings.provided.compliance,
    )

    compliance_source_service = providers.Singleton(
        ComplianceSourceService,
        pravo_by_source_client=pravo_by_source_client,
        settings=settings.provided.compliance,
    )

    routers = List(
        providers.Singleton(HealthRouter),
        providers.Singleton(PingRouter),
        providers.Singleton(AuthRouter),
        providers.Singleton(BotRouter),
        providers.Singleton(IngestionRouter),
        providers.Singleton(
            DiffRouter,
            comparison_job_service=comparison_job_service,
        ),
        providers.Singleton(
            ComplianceRouter,
            compliance_source_service=compliance_source_service,
        ),
        providers.Singleton(ReportRouter),
        providers.Singleton(TenancyRouter),
    )

    middlewares = List(
        CORSHandlingMiddleware,
        ErrorHandlingMiddleware,
    )

    fast_api_app = providers.Singleton(
        FastApiApp,
        db=database,
        redis=async_redis_client,
        settings=settings,
        routers=routers,
        middlewares=middlewares,
    )

    api_runtime = providers.Singleton(
        ApiRuntime,
        application=fast_api_app,
    )

    worker_runtime = providers.Singleton(
        WorkerRuntime,
        settings=settings,
        redis=async_redis_client,
        comparison_job_queue=comparison_job_queue,
        comparison_job_service=comparison_job_service,
    )

    bot_runtime = providers.Singleton(
        BotRuntime,
        settings=settings,
        telegram_bot_service=telegram_bot_service,
        telegram_update_processor=telegram_update_processor,
        telegram_bot_api_client=telegram_bot_api_client,
        telegram_backend_gateway=telegram_backend_gateway,
    )
