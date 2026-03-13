from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic import Field
from pydantic_settings import SettingsConfigDict

from src.auth_manager.config import (
    AuthSettings,
    DatabaseRelationalSettings,
    OpenAISettings,
    RedisSettings,
    Settings,
    StorageSettings,
    TelegramUserAccessEntry,
    TelegramSettings,
    WorkerSettings,
)

_private_key_obj = rsa.generate_private_key(public_exponent=65537, key_size=2048)

class AuthTestSettings(AuthSettings):
    private_key: str = _private_key_obj.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode()

    public_key: str = _private_key_obj.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="allow",
        env_prefix="AM__TEST_AUTH_"
    )


class DatabaseRelationalTestSettings(DatabaseRelationalSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="allow",
        env_prefix="AM__TEST_DB_"
    )

class RedisTestSettings(RedisSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="allow",
        env_prefix="AM__TEST_REDIS_"
    )


class TelegramTestSettings(TelegramSettings):
    bot_token: str = "test-telegram-token"
    api_base_url: str = "http://127.0.0.1:8999"
    backend_updates_url: str = "http://127.0.0.1:8000/bot/telegram/updates"
    polling_timeout_seconds: int = 0
    user_access_map: dict[str, TelegramUserAccessEntry] = Field(
        default_factory=lambda: {
            "42": TelegramUserAccessEntry(
                tenant_slug="acme-mvp",
                tenant_name="Acme MVP",
                username="allowed-42",
                full_name="Allowed User 42",
            ),
            "1001": TelegramUserAccessEntry(
                tenant_slug="acme-mvp",
                tenant_name="Acme MVP",
                username="allowed-1001",
                full_name="Allowed User 1001",
            ),
            "test-user": TelegramUserAccessEntry(
                tenant_slug="acme-mvp",
                tenant_name="Acme MVP",
                username="test-user",
                full_name="Test User",
            ),
        }
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="allow",
        env_prefix="AM__TEST_TELEGRAM_"
    )


class OpenAITestSettings(OpenAISettings):
    api_key: str = "test-openai-key"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="allow",
        env_prefix="AM__TEST_OPENAI_"
    )


class StorageTestSettings(StorageSettings):
    endpoint_url: str = "http://localhost:9000"
    access_key: str = "test-access-key"
    secret_key: str = "test-secret-key"
    bucket: str = "test-bucket"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="allow",
        env_prefix="AM__TEST_STORAGE_"
    )


class WorkerTestSettings(WorkerSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="allow",
        env_prefix="AM__TEST_WORKER_"
    )

class TestSettings(Settings):
    database: DatabaseRelationalTestSettings = Field(default_factory=DatabaseRelationalTestSettings)
    redis: RedisTestSettings = Field(default_factory=RedisTestSettings)
    telegram: TelegramTestSettings = Field(default_factory=TelegramTestSettings)
    openai: OpenAITestSettings = Field(default_factory=OpenAITestSettings)
    storage: StorageTestSettings = Field(default_factory=StorageTestSettings)
    worker: WorkerTestSettings = Field(default_factory=WorkerTestSettings)
    auth: AuthTestSettings = Field(default_factory=AuthTestSettings)

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="allow",
        env_prefix="AM__TEST_"
    )
