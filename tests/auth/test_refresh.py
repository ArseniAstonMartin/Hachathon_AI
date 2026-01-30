import pytest
from dependency_injector.wiring import inject, Provide
from dirty_equals import IsStr
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from src.auth_manager.dto.auth.refresh import RefreshRequest, RefreshRequestPayload


@inject
@pytest.mark.asyncio
async def test_refresh(
        user_regular, redis_client,
        app: FastAPI = Provide["fast_api_app.provided.app"],
        url: str = Provide["settings.provided.url.refresh"]
):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            url,
            json=RefreshRequest(
                payload=RefreshRequestPayload(
                    refresh_token=user_regular['refresh_token'],
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
        assert await redis_client.get(str(user_regular['worker_id'])) != user_regular['refresh_token']
        assert await redis_client.get(str(user_regular['worker_id'])) == IsStr()