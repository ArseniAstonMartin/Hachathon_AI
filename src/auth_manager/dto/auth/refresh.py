from pydantic import BaseModel

from src.auth_manager.components.enums.response_statuses import ResponseStatus
from src.auth_manager.dto.base.response import BaseResponse, BaseResponseMeta


class RefreshRequestPayload(BaseModel):
    refresh_token: str

class RefreshRequest(BaseModel):
    payload: RefreshRequestPayload


class RefreshResponsePayload(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshResponse(
    BaseResponse[RefreshResponsePayload, BaseResponseMeta]
):
    """
    Полноценный ответ на создание категории с payload и meta информацией
    """

    meta: BaseResponseMeta = BaseResponseMeta(status=ResponseStatus.OK, code="200", messages=[])