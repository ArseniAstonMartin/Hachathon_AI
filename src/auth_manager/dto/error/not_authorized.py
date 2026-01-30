from src.auth_manager.components.enums.response_statuses import ResponseStatus
from src.auth_manager.dto.base.response import BaseResponse, BaseResponseMeta, Message


class NotAuthorizedResponse(
    BaseResponse[dict, BaseResponseMeta]
):
    """
    Ответ на ошибку
    """

    meta: BaseResponseMeta = BaseResponseMeta(status=ResponseStatus.ERROR, code="401", messages=[Message(name="error", content="not authorized")])