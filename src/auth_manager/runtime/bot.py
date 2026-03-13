import asyncio
from typing import Any

from src.auth_manager.config import Settings
from src.auth_manager.domains import DOMAIN_DESCRIPTORS
from src.auth_manager.domains.bot.integration import (
    TelegramBackendGateway,
    TelegramBotApiClient,
    TelegramUpdateProcessor,
)
from src.auth_manager.domains.bot.services import TelegramBotService


class BotRuntime:
    def __init__(
        self,
        settings: Settings,
        telegram_bot_service: TelegramBotService,
        telegram_update_processor: TelegramUpdateProcessor,
        telegram_bot_api_client: TelegramBotApiClient,
        telegram_backend_gateway: TelegramBackendGateway,
    ):
        self._settings = settings
        self._telegram_bot_service = telegram_bot_service
        self._telegram_update_processor = telegram_update_processor
        self._telegram_bot_api_client = telegram_bot_api_client
        self._telegram_backend_gateway = telegram_backend_gateway
        self._domains = tuple(
            descriptor for descriptor in DOMAIN_DESCRIPTORS if descriptor.layer == "bot"
        )

    @property
    def update_mode(self) -> str:
        return self._settings.telegram.update_mode

    @property
    def domains(self):
        return self._domains

    async def handle_update(self, user_id: str | int, text: str) -> dict[str, str]:
        event = await self._telegram_update_processor.process(
            self.build_text_update(user_id=user_id, text=text)
        )
        if event is None:
            raise ValueError("Telegram update could not be processed")
        return {
            "message": event.reply_message,
            "dialog_state": event.dialog_state,
        }

    def get_dialog_state(self, user_id: str | int) -> str:
        return self._telegram_bot_service.get_dialog_state(user_id)

    def startup_summary(self) -> str:
        domain_names = ", ".join(descriptor.name for descriptor in self._domains)
        return (
            f"Bot runtime is ready in {self.update_mode} mode "
            f"for domains: {domain_names}"
        )

    @staticmethod
    def build_text_update(user_id: str | int, text: str, update_id: int = 0) -> dict[str, Any]:
        normalized_user_id = int(user_id) if str(user_id).isdigit() else str(user_id)
        return {
            "update_id": update_id,
            "message": {
                "message_id": update_id,
                "from": {"id": normalized_user_id, "is_bot": False},
                "chat": {"id": normalized_user_id, "type": "private"},
                "text": text,
            },
        }

    async def run(self) -> None:
        if self.update_mode == "polling":
            await self.run_polling()
            return
        await self.run_stdio()

    async def run_polling(self) -> None:
        print(self.startup_summary())
        next_offset: int | None = None
        while True:
            updates = await self._telegram_bot_api_client.get_updates(offset=next_offset)
            for update in updates:
                await self.process_polled_update(update)
                update_id = update.get("update_id")
                if isinstance(update_id, int):
                    next_offset = update_id + 1
            if not updates:
                await asyncio.sleep(1)

    async def process_polled_update(self, update: dict[str, Any]) -> dict[str, Any]:
        result = await self._telegram_backend_gateway.deliver_update(update)
        reply_message = result.get("reply_message")
        chat_id = result.get("chat_id")
        if reply_message and chat_id:
            await self._telegram_bot_api_client.send_message(chat_id=str(chat_id), text=str(reply_message))
        return result

    async def run_stdio(self) -> None:
        print(self.startup_summary())
        print("Enter commands as '<user_id> /start|/help|/compare'. Press Ctrl+C to stop.")

        while True:
            try:
                raw_line = input("> ").strip()
            except EOFError:
                break
            if not raw_line:
                continue

            user_id, _, text = raw_line.partition(" ")
            if not text:
                print("Expected format: <user_id> <command>")
                continue

            reply = await self.handle_update(user_id=user_id, text=text)
            print(f"[state={reply['dialog_state']}] {reply['message']}")
