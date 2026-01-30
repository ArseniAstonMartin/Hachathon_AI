import pytest
from dependency_injector.wiring import inject, Provide
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport


@inject
@pytest.mark.asyncio
async def test_me(
        user_admin,
        app: FastAPI = Provide["fast_api_app.provided.app"],
        url: str = Provide["settings.provided.url.me"]
):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(
            url,
            headers={"Authorization": f"Bearer {user_admin['access_token']}"}
        )
        assert response.status_code == 200
        data = response.json()

        assert data["payload"]["email"] == user_admin['email']
        assert str(data["payload"]["id"]) == str(user_admin['worker_id'])
        assert data["meta"]["status"] == "OK"