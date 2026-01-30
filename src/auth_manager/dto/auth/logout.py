from pydantic import BaseModel
from src.auth_manager.components.enums.response_statuses import ResponseStatus
from src.auth_manager.dto.base.response import BaseResponse, BaseResponseMeta

class LogoutResponsePayload(BaseModel):
    """
    Пустой payload для ответа на выход из системы
    """
    pass

class LogoutResponse(
    BaseResponse[LogoutResponsePayload, BaseResponseMeta]
):
    """
    Полноценный ответ на logout с пустым payload и meta информацией
    """
    meta: BaseResponseMeta = BaseResponseMeta(status=ResponseStatus.OK, code="200", messages=[])