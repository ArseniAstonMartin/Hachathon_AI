import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src.auth_manager.components.register_modules import register_modules
from src.auth_manager.di import DependencyInjector
from tests.config import TestSettings

pytest_plugins = [
    "tests.fixtures",
    "pytest_asyncio"
]

@pytest.fixture(scope="session", autouse=True)
def container():
    DependencyInjector.settings.override(TestSettings())
    register_modules(package_name="src", container=DependencyInjector)
    container = DependencyInjector()
    container.wire(packages=["."])
    yield container
    container.unwire()


@pytest.fixture(scope="session")
def event_loop():
    import asyncio
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def prepare_database_for_test(container):
    settings = TestSettings()
    db_s = settings.database
    db_name = getattr(db_s, "name", getattr(db_s, "database", "test"))

    root_url = f"postgresql+asyncpg://{db_s.user}:{db_s.password}@{db_s.host}:{db_s.port}/postgres"
    root_engine = create_async_engine(root_url, isolation_level="AUTOCOMMIT")
    async with root_engine.connect() as conn:
        check_db = await conn.execute(text(f"SELECT 1 FROM pg_database WHERE datname='{db_name}'"))
        if not check_db.scalar():
            await conn.execute(text(f"CREATE DATABASE {db_name}"))
    await root_engine.dispose()

    db_component = container.database()
    session = await db_component.get_session()
    try:
        await session.execute(text("DROP SCHEMA public CASCADE"))
        await session.execute(text("CREATE SCHEMA public"))
        await session.execute(text("""
            CREATE TABLE worker_base (
                worker_id SERIAL PRIMARY KEY,
                email VARCHAR NOT NULL UNIQUE,
                password VARCHAR(128),
                is_localadmin BOOLEAN DEFAULT FALSE,
                is_admin BOOLEAN DEFAULT FALSE,
                is_active BOOLEAN DEFAULT TRUE,
                first_name VARCHAR,
                last_name VARCHAR,
                middle_name VARCHAR
            );
        """))
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise e
    finally:
        await session.close()

@pytest_asyncio.fixture(scope="function")
async def redis_client(container):
    return await container.async_redis_client().client