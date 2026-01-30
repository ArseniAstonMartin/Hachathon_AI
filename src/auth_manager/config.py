import os
from typing import Optional

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic import field_validator
from pydantic_settings import SettingsConfigDict
from pydantic_settings import BaseSettings
from pydantic import ValidationInfo

private_key_obj = rsa.generate_private_key(public_exponent=65537, key_size=2048)

private_key_pem = private_key_obj.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
).decode('utf-8')

public_key_pem = private_key_obj.public_key().public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo
).decode('utf-8')

class DatabaseRelationalSettings(BaseSettings):
    host: str
    port: str
    name: str
    user: str
    password: str
    url: Optional[str] = None

    @field_validator("url", mode="before")
    @classmethod
    def assemble_url(cls, v: Optional[str], info: ValidationInfo) -> str:
        if isinstance(v, str):
            return v

        data = info.data
        return f"postgresql+asyncpg://{data['user']}:{data['password']}@{data['host']}:{data['port']}/{data['name']}"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="allow",
        env_prefix="AM__DB_"
    )

class RedisSettings(BaseSettings):
    host: str
    port: str
    password: str
    db: int = 0

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="allow",
        env_prefix="AM__REDIS_"
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

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="allow",
        env_prefix="AM__URL_"
    )

class AppSettings(BaseSettings):
    name: str = "FastAPI Auth Service"
    log_level: str = "DEBUG"
    dev_mode: bool = False
    root_path: str = "/auth_api"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="allow",
        env_prefix="AM__APP_"
    )

class AuthSettings(BaseSettings):
    private_key: Optional[str] = None
    public_key: Optional[str] = None
    algorithm: str = "RS256"
    access_expires_delta: int = 15
    refresh_expires_delta: int = 2160

    @field_validator("private_key", mode="before")
    @classmethod
    def assemble_private_key(cls, v: Optional[str], info: ValidationInfo) -> str:
        if isinstance(v, str) and v.strip():
            return v

        if os.path.exists("private.pem"):
            with open("private.pem", "r") as f:
                return f.read()

        return private_key_pem

    @field_validator("public_key", mode="before")
    @classmethod
    def assemble_public_key(cls, v: Optional[str], info: ValidationInfo) -> str:
        if isinstance(v, str) and v.strip():
            return v

        if os.path.exists("public.pem"):
            with open("public.pem", "r") as f:
                return f.read()

        return public_key_pem



class Settings(BaseSettings):
    database: DatabaseRelationalSettings = DatabaseRelationalSettings()
    redis: RedisSettings = RedisSettings()
    url: UrlSettings = UrlSettings()
    app: AppSettings = AppSettings()
    auth: AuthSettings = AuthSettings()