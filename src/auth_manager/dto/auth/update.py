from pydantic import BaseModel, Field
from typing import Optional
from src.auth_manager.components.enums.response_statuses import ResponseStatus
from src.auth_manager.dto.base.response import BaseResponse, BaseResponseMeta
from src.auth_manager.dto.auth.me import MeResponsePayload

class UpdateMeRequestPayload(BaseModel):
    first_name: Optional[str] = Field(None, min_length=1)
    last_name: Optional[str] = Field(None, min_length=1)
    middle_name: Optional[str] = Field(None, min_length=1)

class UpdateMeRequest(BaseModel):
    payload: UpdateMeRequestPayload

class UpdateMeResponse(BaseResponse[MeResponsePayload, BaseResponseMeta]):
    meta: BaseResponseMeta = BaseResponseMeta(status=ResponseStatus.OK, code="200", messages=[])