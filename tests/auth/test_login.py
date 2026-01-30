import os
import sys

import pytest
from dependency_injector.wiring import Provide, inject
from dirty_equals import IsStr
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from src.auth_manager.dto.auth.login import LoginRequest, LoginRequestPayload

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))


@inject
@pytest.mark.asyncio
async def test_login_admin(
        user_admin, redis_client,
        app: FastAPI = Provide["fast_api_app.provided.app"],
        url: str = Provide["settings.provided.url.login"]
):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            url,
            json=LoginRequest(
                payload=LoginRequestPayload(
                    email="admin@example.com",
                    password="adminadmin"
                )
            ).model_dump()
        )
        assert response.status_code == 200
        assert response.json() == {
            "payload": {
                "access_token": IsStr(),
                "refresh_token": IsStr(),
                "token_type": IsStr()
            },
            "meta": {
                "status": "OK",
                "code": "200",
                "messages": []
            }
        }
        assert await redis_client.get(str(user_admin['worker_id'])) == IsStr()
        assert await redis_client.get(str(user_admin['worker_id'])) != user_admin['refresh_token']

@inject
@pytest.mark.asyncio
async def test_login_user(
        user_regular, redis_client,
        app: FastAPI = Provide["fast_api_app.provided.app"],
        url: str = Provide["settings.provided.url.login"]
):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            url,
            json=LoginRequest(
                payload=LoginRequestPayload(
                    email="user@example.com",
                    password="adminadmin"
                )
            ).model_dump()
        )
        assert response.status_code == 200
        assert response.json() == {
            "payload": {
                "access_token": IsStr(),
                "refresh_token": IsStr(),
                "token_type": IsStr()
            },
            "meta": {
                "status": "OK",
                "code": "200",
                "messages": []
            }
        }
        assert await redis_client.get(str(user_regular['worker_id'])) == IsStr()
        assert await redis_client.get(str(user_regular['worker_id'])) != user_regular['refresh_token']