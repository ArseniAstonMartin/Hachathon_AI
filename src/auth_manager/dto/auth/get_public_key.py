from pydantic import BaseModel

from src.auth_manager.components.enums.response_statuses import ResponseStatus
from src.auth_manager.dto.base.response import BaseResponse, BaseResponseMeta


class GetPublicKeyPayload(BaseModel):
    public_key: str

class GetPublicKeyResponse(
    BaseResponse[GetPublicKeyPayload, BaseResponseMeta]
):
    """
    Полноценный ответ на создание категории с payload и meta информацией
    """

    meta: BaseResponseMeta = BaseResponseMeta(status=ResponseStatus.OK, code="200", messages=[])