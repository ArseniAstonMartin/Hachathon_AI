from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select

from src.auth_manager.components.database.relation.async_database import AsyncDatabaseRelational
from src.auth_manager.components.injectable import injectable
from src.auth_manager.config import Settings, TelegramUserAccessEntry
from src.auth_manager.models import Tenant, TenantStatus, User


@dataclass(frozen=True, slots=True)
class ResolvedTelegramPrincipal:
    telegram_user_id: str
    internal_user_id: str
    tenant_id: str
    tenant_slug: str
    username: str | None
    full_name: str | None


@dataclass(frozen=True, slots=True)
class TelegramAccessDenied:
    telegram_user_id: str
    message: str


@injectable()
class TelegramPrincipalResolver:
    def __init__(
        self,
        settings: Settings,
        db: AsyncDatabaseRelational,
    ) -> None:
        self._settings = settings
        self._db = db

    async def resolve(
        self,
        telegram_user_id: str | int,
        telegram_username: str | None = None,
        telegram_full_name: str | None = None,
    ) -> ResolvedTelegramPrincipal | TelegramAccessDenied:
        normalized_user_id = str(telegram_user_id)
        mapping = self._settings.telegram.user_access_map.get(normalized_user_id)
        if mapping is None:
            return TelegramAccessDenied(
                telegram_user_id=normalized_user_id,
                message=(
                    "Доступ к MVP не настроен для этого Telegram аккаунта. "
                    "Обратитесь к администратору, чтобы получить доступ."
                ),
            )

        session = await self._db.get_session()
        try:
            tenant = await session.scalar(select(Tenant).where(Tenant.slug == mapping.tenant_slug))
            if tenant is None:
                tenant = Tenant(
                    name=self._resolve_tenant_name(mapping),
                    slug=mapping.tenant_slug,
                )
                session.add(tenant)
                await session.flush()

            if tenant.status != TenantStatus.ACTIVE:
                return TelegramAccessDenied(
                    telegram_user_id=normalized_user_id,
                    message=(
                        "Доступ временно недоступен: tenant отключен. "
                        "Обратитесь к администратору."
                    ),
                )

            user = await session.scalar(select(User).where(User.telegram_user_id == normalized_user_id))
            if user is not None and user.tenant_id != tenant.id:
                return TelegramAccessDenied(
                    telegram_user_id=normalized_user_id,
                    message=(
                        "Конфигурация доступа для этого Telegram аккаунта некорректна. "
                        "Обратитесь к администратору."
                    ),
                )

            resolved_username = telegram_username or mapping.username
            resolved_full_name = telegram_full_name or mapping.full_name

            if user is None:
                user = User(
                    tenant_id=tenant.id,
                    telegram_user_id=normalized_user_id,
                    username=resolved_username,
                    full_name=resolved_full_name,
                )
                session.add(user)
                await session.flush()
            else:
                user.username = resolved_username or user.username
                user.full_name = resolved_full_name or user.full_name

            user.last_seen_at = datetime.now(timezone.utc)
            await session.commit()

            return ResolvedTelegramPrincipal(
                telegram_user_id=normalized_user_id,
                internal_user_id=str(user.id),
                tenant_id=str(tenant.id),
                tenant_slug=tenant.slug,
                username=user.username,
                full_name=user.full_name,
            )
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    @staticmethod
    def _resolve_tenant_name(mapping: TelegramUserAccessEntry) -> str:
        if mapping.tenant_name:
            return mapping.tenant_name
        return mapping.tenant_slug.replace("-", " ").strip().title()
