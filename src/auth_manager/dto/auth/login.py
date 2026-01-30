from pydantic import BaseModel

from src.auth_manager.components.enums.response_statuses import ResponseStatus
from src.auth_manager.dto.base.response import BaseResponse, BaseResponseMeta


class LoginRequestPayload(BaseModel):
    email: str
    password: str

class LoginRequest(BaseModel):
    payload: LoginRequestPayload


class LoginResponsePayload(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class LoginResponse(
    BaseResponse[LoginResponsePayload, BaseResponseMeta]
):
    """
    Полноценный ответ на создание категории с payload и meta информацией
    """

    meta: BaseResponseMeta = BaseResponseMeta(status=ResponseStatus.OK, code="200", messages=[])