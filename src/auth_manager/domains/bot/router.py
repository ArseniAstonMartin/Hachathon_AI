from typing import Any

from dependency_injector.wiring import Provide, inject
from fastapi import Header, HTTPException, status

from src.auth_manager.components.enums.http_methods import HTTPMethod
from src.auth_manager.config import Settings
from src.auth_manager.domains.bot.integration import TelegramBotApiClient, TelegramUpdateProcessor
from src.auth_manager.routers.base import BaseRouter


class BotRouter(BaseRouter):
    @inject
    def __init__(
        self,
        settings: Settings = Provide["settings"],
        telegram_update_processor: TelegramUpdateProcessor = Provide["telegram_update_processor"],
        telegram_bot_api_client: TelegramBotApiClient = Provide["telegram_bot_api_client"],
    ):
        self._settings = settings
        self._telegram_update_processor = telegram_update_processor
        self._telegram_bot_api_client = telegram_bot_api_client
        super().__init__()

    def _init_routes(self):
        self.init_handler(self.__overview, HTTPMethod.GET, "/bot")
        self.init_handler(self.__handle_update, HTTPMethod.POST, "/bot/telegram/updates")
        self.init_handler(self.__handle_webhook, HTTPMethod.POST, "/bot/telegram/webhook")
        self.init_handler(self.__events, HTTPMethod.GET, "/bot/telegram/events")

    async def __overview(self) -> dict[str, str | list[str]]:
        return {
            "domain": "bot",
            "status": "ready",
            "capabilities": [
                "telegram-entrypoint",
                "telegram-webhook",
                "telegram-polling-bridge",
                "user-dialog-state",
            ],
        }

    async def __handle_update(self, update: dict[str, Any]) -> dict[str, Any]:
        processed_update = await self._telegram_update_processor.process(update)
        if processed_update is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported Telegram update payload",
            )
        return {
            "status": "processed",
            "update_id": processed_update.update_id,
            "chat_id": processed_update.chat_id,
            "user_id": processed_update.telegram_user_id,
            "internal_user_id": processed_update.internal_user_id,
            "tenant_id": processed_update.tenant_id,
            "tenant_slug": processed_update.tenant_slug,
            "event_type": processed_update.event_type,
            "reply_message": processed_update.reply_message,
            "dialog_state": processed_update.dialog_state,
            "content_preview": processed_update.content_preview,
            "document_id": processed_update.document_id,
            "storage_path": processed_update.storage_path,
            "checksum": processed_update.checksum,
            "size_bytes": processed_update.size_bytes,
        }

    async def __handle_webhook(
        self,
        update: dict[str, Any],
        x_telegram_bot_api_secret_token: str | None = Header(default=None),
    ) -> dict[str, str]:
        expected_secret = self._settings.telegram.webhook_secret
        if expected_secret and x_telegram_bot_api_secret_token != expected_secret:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Telegram webhook secret",
            )

        processed_update = await self._telegram_update_processor.process(update)
        if processed_update is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported Telegram update payload",
            )

        await self._telegram_bot_api_client.send_message(
            chat_id=processed_update.chat_id,
            text=processed_update.reply_message,
        )
        return {"status": "accepted"}

    async def __events(self) -> dict[str, list[dict[str, Any]]]:
        return {"events": self._telegram_update_processor.recent_events()}
