from src.auth_manager.components.enums.response_statuses import ResponseStatus
from src.auth_manager.dto.base.response import BaseResponse, BaseResponseMeta


class PingResponse(
    BaseResponse[dict, BaseResponseMeta]
):
    """
    Полноценный ответ на ping
    """

    meta: BaseResponseMeta = BaseResponseMeta(status=ResponseStatus.OK, code="200", messages=[])