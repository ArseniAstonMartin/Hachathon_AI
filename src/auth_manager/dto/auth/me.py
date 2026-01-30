from pydantic import BaseModel
from typing import Optional

from src.auth_manager.components.enums.response_statuses import ResponseStatus
from src.auth_manager.dto.base.response import BaseResponse, BaseResponseMeta


class MeResponsePayload(BaseModel):
    id: str
    email: Optional[str]
    role: Optional[str]
    first_name: Optional[str]
    middle_name: Optional[str]
    last_name: Optional[str]

class MeResponse(
    BaseResponse[MeResponsePayload, BaseResponseMeta]
):
    """
    Полноценный ответ на создание категории с payload и meta информацией
    """

    meta: BaseResponseMeta = BaseResponseMeta(status=ResponseStatus.OK, code="200", messages=[])