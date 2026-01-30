from src.auth_manager.dto.base.response import BaseResponse, BaseResponseMeta


class HttpExceptionResponse(
    BaseResponse[dict, BaseResponseMeta]
):
    """
    Ответ на ошибку
    """

    meta: BaseResponseMeta