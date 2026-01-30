import pytest
from dependency_injector.wiring import Provide, inject
from dirty_equals import IsInt
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport


@inject
@pytest.mark.asyncio
async def test_register_success(
        app: FastAPI = Provide["fast_api_app.provided.app"],
        url: str = Provide["settings.provided.url.register"]
):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "payload": {
                "email": "new_user@example.com",
                "password": "password123",
                "password_repeat": "password123",
                "first_name": "Ivan",
                "last_name": "Ivanov",
                "middle_name": "Ivanovich"
            }
        }
        response = await ac.post(url, json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["meta"]["status"] == "OK"
        assert data["payload"]["email"] == "new_user@example.com"
        assert isinstance(data["payload"]["worker_id"], str)