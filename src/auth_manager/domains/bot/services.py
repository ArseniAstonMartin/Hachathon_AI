from __future__ import annotations

from dataclasses import dataclass

from src.auth_manager.components.injectable import injectable


AWAITING_SOURCE_DOCUMENT = "awaiting_source_document"
AWAITING_TARGET_DOCUMENT = "awaiting_target_document"
IDLE_DIALOG_STATE = "idle"


@dataclass(frozen=True, slots=True)
class BotReply:
    message: str
    dialog_state: str


@injectable()
class BotDialogStateStore:
    def __init__(self) -> None:
        self._state_by_user: dict[str, str] = {}

    def set_state(self, user_id: str, state: str) -> None:
        self._state_by_user[user_id] = state

    def get_state(self, user_id: str) -> str:
        return self._state_by_user.get(user_id, IDLE_DIALOG_STATE)


@injectable()
class TelegramBotService:
    def __init__(self, dialog_state_store: BotDialogStateStore):
        self._dialog_state_store = dialog_state_store

    async def handle_message(self, user_id: str | int, text: str) -> BotReply:
        normalized_user_id = str(user_id)
        command = text.strip().split(maxsplit=1)[0].lower()

        if command == "/start":
            self._dialog_state_store.set_state(normalized_user_id, IDLE_DIALOG_STATE)
            return BotReply(
                message=(
                    "Привет. Я помогаю сравнить две версии документа для MVP. "
                    "Сначала запустите /compare, затем отправьте старую и новую редакции."
                ),
                dialog_state=IDLE_DIALOG_STATE,
            )

        if command == "/help":
            return BotReply(
                message=(
                    "Поддерживаются два файла в форматах .docx и .pdf. "
                    "Сначала отправьте старую редакцию, потом новую. "
                    "Неподдерживаемые форматы и слишком большие файлы будут отклонены."
                ),
                dialog_state=self._dialog_state_store.get_state(normalized_user_id),
            )

        if command == "/compare":
            self._dialog_state_store.set_state(
                normalized_user_id,
                AWAITING_SOURCE_DOCUMENT,
            )
            return BotReply(
                message=(
                    "Начинаем новый анализ. Отправьте старую редакцию документа "
                    "в формате .docx или .pdf."
                ),
                dialog_state=AWAITING_SOURCE_DOCUMENT,
            )

        return BotReply(
            message="Неизвестная команда. Используйте /start, /help или /compare.",
            dialog_state=self._dialog_state_store.get_state(normalized_user_id),
        )

    def get_dialog_state(self, user_id: str | int) -> str:
        return self._dialog_state_store.get_state(str(user_id))

    def set_dialog_state(self, user_id: str | int, state: str) -> None:
        self._dialog_state_store.set_state(str(user_id), state)
