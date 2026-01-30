import pytest
from dependency_injector.wiring import Provide, inject
from dirty_equals import IsStr
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


@inject
@pytest.mark.asyncio
async def test_get_public_key(
        app: FastAPI = Provide["fast_api_app.provided.app"],
        url: str = Provide["settings.provided.url.get_public_key"]
):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(
            url
        )
        assert response.status_code == 200
        assert response.json() == {
            "payload": {
                "public_key": IsStr(),
            },
            "meta": {
                "status": "OK",
                "code": "200",
                "messages": []
            }
        }