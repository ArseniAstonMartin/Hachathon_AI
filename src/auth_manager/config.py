import os
from typing import Literal, Optional

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic import BaseModel, Field, ValidationError, ValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

private_key_obj = rsa.generate_private_key(public_exponent=65537, key_size=2048)

private_key_pem = private_key_obj.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
).decode("utf-8")

public_key_pem = private_key_obj.public_key().public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo
).decode("utf-8")

SETTINGS_MODEL_CONFIG = SettingsConfigDict(
    env_file=".env",
    extra="allow",
)

SETTINGS_ENV_PREFIXES = {
    "database": "AM__DB_",
    "redis": "AM__REDIS_",
    "telegram": "AM__TELEGRAM_",
    "url": "AM__URL_",
    "app": "AM__APP_",
    "openai": "AM__OPENAI_",
    "storage": "AM__STORAGE_",
    "worker": "AM__WORKER_",
    "auth": "AM__AUTH_",
    "compliance": "AM__COMPLIANCE_",
}

SETTINGS_TITLES_TO_SECTIONS = {
    "DatabaseRelationalSettings": "database",
    "RedisSettings": "redis",
    "TelegramSettings": "telegram",
    "UrlSettings": "url",
    "AppSettings": "app",
    "OpenAISettings": "openai",
    "StorageSettings": "storage",
    "WorkerSettings": "worker",
    "AuthSettings": "auth",
    "ComplianceSettings": "compliance",
}


class ConfigurationError(RuntimeError):
    pass


def _env_var_name(location: tuple[object, ...]) -> str:
    if not location:
        return "unknown"

    section = str(location[0])
    prefix = SETTINGS_ENV_PREFIXES.get(section)
    field_parts = location[1:] if prefix else location
    suffix = "__".join(str(part).upper() for part in field_parts)

    if prefix:
        return f"{prefix}{suffix}" if suffix else prefix.rstrip("_")

    return "__".join(str(part).upper() for part in location)


def _format_validation_error(
    error: ValidationError,
    section_name: Optional[str] = None,
) -> str:
    missing_vars: set[str] = set()
    invalid_fields: list[str] = []

    for issue in error.errors():
        location = tuple(issue.get("loc", ()))
        if section_name:
            location = (section_name, *location)

        env_name = _env_var_name(location)
        if issue.get("type") == "missing":
            missing_vars.add(env_name)
            continue

        invalid_fields.append(f"{env_name}: {issue.get('msg', 'Invalid value')}")

    parts = ["Configuration error detected during startup."]
    if missing_vars:
        parts.append(
            "Missing required environment variables: "
            + ", ".join(sorted(missing_vars))
        )
    if invalid_fields:
        parts.append("Invalid configuration values: " + "; ".join(invalid_fields))

    return " ".join(parts)


class DatabaseRelationalSettings(BaseSettings):
    host: str
    port: str
    name: str
    user: str
    password: str
    url: Optional[str] = None

    @field_validator("url", mode="before")
    @classmethod
    def assemble_url(cls, value: Optional[str], info: ValidationInfo) -> str:
        if isinstance(value, str) and value.strip():
            return value

        data = info.data
        return (
            f"postgresql+asyncpg://{data['user']}:{data['password']}"
            f"@{data['host']}:{data['port']}/{data['name']}"
        )

    model_config = SettingsConfigDict(**SETTINGS_MODEL_CONFIG, env_prefix="AM__DB_")


class RedisSettings(BaseSettings):
    host: str
    port: str
    password: str
    db: int = 0

    model_config = SettingsConfigDict(**SETTINGS_MODEL_CONFIG, env_prefix="AM__REDIS_")


class TelegramUserAccessEntry(BaseModel):
    tenant_slug: str
    tenant_name: Optional[str] = None
    username: Optional[str] = None
    full_name: Optional[str] = None


class TelegramSettings(BaseSettings):
    bot_token: str
    bot_username: Optional[str] = None
    update_mode: Literal["polling", "webhook"] = "polling"
    api_base_url: str = "https://api.telegram.org"
    backend_updates_url: str = "http://127.0.0.1:8000/bot/telegram/updates"
    polling_timeout_seconds: int = 30
    max_document_size_bytes: int = 10 * 1024 * 1024
    webhook_base_url: Optional[str] = None
    webhook_secret: Optional[str] = None
    user_access_map: dict[str, TelegramUserAccessEntry] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_webhook_mode(self) -> "TelegramSettings":
        if self.update_mode != "webhook":
            return self

        missing_vars = []
        if not self.webhook_base_url:
            missing_vars.append("AM__TELEGRAM_WEBHOOK_BASE_URL")
        if not self.webhook_secret:
            missing_vars.append("AM__TELEGRAM_WEBHOOK_SECRET")

        if missing_vars:
            raise ValueError("Webhook mode requires: " + ", ".join(missing_vars))

        return self

    model_config = SettingsConfigDict(
        **SETTINGS_MODEL_CONFIG,
        env_prefix="AM__TELEGRAM_"
    )


class UrlSettings(BaseSettings):
    register: str = "/register"
    login: str = "/login"
    refresh: str = "/refresh"
    me: str = "/me"
    get_public_key: str = "/get_public_key"
    logout: str = "/logout"
    update_me: str = "/me"
    delete_me: str = "/me"
    admin_check: str = "/admin/check"
    ping: str = "/ping"

    model_config = SettingsConfigDict(**SETTINGS_MODEL_CONFIG, env_prefix="AM__URL_")


class AppSettings(BaseSettings):
    name: str = "FastAPI Auth Service"
    log_level: str = "DEBUG"
    dev_mode: bool = False
    root_path: str = "/auth_api"

    model_config = SettingsConfigDict(**SETTINGS_MODEL_CONFIG, env_prefix="AM__APP_")


class OpenAISettings(BaseSettings):
    api_key: str
    model: str = "gpt-5-mini"
    base_url: Optional[str] = None

    model_config = SettingsConfigDict(
        **SETTINGS_MODEL_CONFIG,
        env_prefix="AM__OPENAI_"
    )


class StorageSettings(BaseSettings):
    endpoint_url: str
    access_key: str
    secret_key: str
    bucket: str
    region: str = "us-east-1"
    secure: bool = False

    model_config = SettingsConfigDict(
        **SETTINGS_MODEL_CONFIG,
        env_prefix="AM__STORAGE_"
    )


class WorkerSettings(BaseSettings):
    queue_name: str = "comparison-jobs"
    concurrency: int = 1
    job_timeout_seconds: int = 900
    result_ttl_seconds: int = 3600

    model_config = SettingsConfigDict(
        **SETTINGS_MODEL_CONFIG,
        env_prefix="AM__WORKER_"
    )


class AuthSettings(BaseSettings):
    private_key: Optional[str] = None
    public_key: Optional[str] = None
    algorithm: str = "RS256"
    access_expires_delta: int = 15
    refresh_expires_delta: int = 2160

    @field_validator("private_key", mode="before")
    @classmethod
    def assemble_private_key(cls, value: Optional[str], info: ValidationInfo) -> str:
        if isinstance(value, str) and value.strip():
            return value

        if os.path.exists("private.pem"):
            with open("private.pem", "r") as private_key_file:
                return private_key_file.read()

        return private_key_pem

    @field_validator("public_key", mode="before")
    @classmethod
    def assemble_public_key(cls, value: Optional[str], info: ValidationInfo) -> str:
        if isinstance(value, str) and value.strip():
            return value

        if os.path.exists("public.pem"):
            with open("public.pem", "r") as public_key_file:
                return public_key_file.read()

        return public_key_pem

    model_config = SettingsConfigDict(**SETTINGS_MODEL_CONFIG, env_prefix="AM__AUTH_")


class ComplianceSettings(BaseSettings):
    pravo_by_base_url: str = "https://pravo.by"
    request_timeout_seconds: float = 15.0
    min_interval_seconds: float = 1.0
    max_publication_results: int = 20
    user_agent: str = "FastAPIAuthService/0.0.0 (+https://pravo.by)"

    model_config = SettingsConfigDict(
        **SETTINGS_MODEL_CONFIG,
        env_prefix="AM__COMPLIANCE_"
    )


class Settings(BaseSettings):
    database: DatabaseRelationalSettings = Field(default_factory=DatabaseRelationalSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    telegram: TelegramSettings = Field(default_factory=TelegramSettings)
    url: UrlSettings = Field(default_factory=UrlSettings)
    app: AppSettings = Field(default_factory=AppSettings)
    openai: OpenAISettings = Field(default_factory=OpenAISettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    worker: WorkerSettings = Field(default_factory=WorkerSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    compliance: ComplianceSettings = Field(default_factory=ComplianceSettings)

    model_config = SETTINGS_MODEL_CONFIG


def load_settings() -> Settings:
    try:
        loaded_sections = {
            "database": DatabaseRelationalSettings(),
            "redis": RedisSettings(),
            "telegram": TelegramSettings(),
            "url": UrlSettings(),
            "app": AppSettings(),
            "openai": OpenAISettings(),
            "storage": StorageSettings(),
            "worker": WorkerSettings(),
            "auth": AuthSettings(),
            "compliance": ComplianceSettings(),
        }
    except ValidationError as error:
        raise ConfigurationError(
            _format_validation_error(
                error,
                section_name=SETTINGS_TITLES_TO_SECTIONS.get(error.title),
            )
        ) from error

    try:
        return Settings(**loaded_sections)
    except ValidationError as error:
        raise ConfigurationError(_format_validation_error(error)) from error
