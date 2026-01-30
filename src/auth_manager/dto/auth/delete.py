from pydantic import BaseModel
from src.auth_manager.components.enums.response_statuses import ResponseStatus
from src.auth_manager.dto.base.response import BaseResponse, BaseResponseMeta

class DeleteMeResponsePayload(BaseModel):
    success: bool = True

class DeleteMeResponse(BaseResponse[DeleteMeResponsePayload, BaseResponseMeta]):
    meta: BaseResponseMeta = BaseResponseMeta(status=ResponseStatus.OK, code="200", messages=[])