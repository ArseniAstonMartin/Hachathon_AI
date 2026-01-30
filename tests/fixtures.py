import pytest_asyncio
import bcrypt
from datetime import datetime, timedelta, timezone
from jose import jwt
from sqlalchemy import text


async def _prepare_user_fixture(container, redis_client, user_id, email, role, is_admin, is_local):
    session = await container.database().get_session()
    auth_service = container.auth_service()

    raw_password = "adminadmin"
    salt = auth_service._get_salt(email)
    hashed_password = "sha256$" + bcrypt.hashpw(raw_password.encode(), salt).decode()

    user_data = {
        "worker_id": user_id,
        "email": email,
        "password": hashed_password,
        "is_localadmin": is_local,
        "is_admin": is_admin,
        "first_name": "Test",
        "last_name": "User",
        "middle_name": "Testovich",
        "is_active": True
    }

    private_key = container.settings().auth.private_key
    algorithm = container.settings().auth.algorithm

    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "first_name": user_data["first_name"],
        "last_name": user_data["last_name"],
        "middle_name": user_data["middle_name"]
    }
    expire = datetime.now(timezone.utc) + timedelta(minutes=10)
    payload.update({"exp": expire})

    token = jwt.encode(payload, private_key, algorithm=algorithm)

    await redis_client.set(str(user_id), token, ex=600)
    user_data['access_token'] = token
    user_data['refresh_token'] = token

    await session.execute(text("""
        INSERT INTO worker_base (worker_id, email, password, is_localadmin, is_admin, first_name, last_name, middle_name, is_active)
        VALUES (:worker_id, :email, :password, :is_localadmin, :is_admin, :first_name, :last_name, :middle_name, :is_active)
    """), user_data)
    await session.commit()

    return user_data, session


@pytest_asyncio.fixture(scope="function")
async def user_regular(container, redis_client):
    user_data, session = await _prepare_user_fixture(
        container, redis_client, 1, "user@example.com", "user", False, False
    )
    yield user_data
    await session.execute(text("DELETE FROM worker_base WHERE worker_id = 1"))
    await session.commit()
    await session.close()


@pytest_asyncio.fixture(scope="function")
async def user_admin(container, redis_client):
    user_data, session = await _prepare_user_fixture(
        container, redis_client, 2, "admin@example.com", "admin", True, True
    )
    yield user_data
    await session.execute(text("DELETE FROM worker_base WHERE worker_id = 2"))
    await session.commit()
    await session.close()