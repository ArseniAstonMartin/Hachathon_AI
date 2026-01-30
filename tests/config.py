from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic_settings import SettingsConfigDict

from src.auth_manager.config import RedisSettings, DatabaseRelationalSettings, Settings, AuthSettings

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

class TestSettings(Settings):
    database: DatabaseRelationalTestSettings = DatabaseRelationalTestSettings()
    redis: RedisTestSettings = RedisTestSettings()
    auth: AuthTestSettings = AuthTestSettings()

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="allow",
        env_prefix="AM__TEST_"
    )