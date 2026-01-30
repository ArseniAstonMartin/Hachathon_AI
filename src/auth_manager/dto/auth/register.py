import re
from typing import Optional
from pydantic import BaseModel, field_validator, model_validator

from src.auth_manager.components.enums.response_statuses import ResponseStatus
from src.auth_manager.dto.base.response import BaseResponse, BaseResponseMeta
from src.auth_manager.components.exceptions import BadRequestException


class RegisterRequestPayload(BaseModel):
    email: str
    password: str
    password_repeat: str
    first_name: str
    last_name: str
    middle_name: Optional[str] = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        email_regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        if not re.match(email_regex, v):
            raise BadRequestException("Invalid email format")
        return v.lower()

    @model_validator(mode="after")
    def check_passwords_match(self) -> "RegisterRequestPayload":
        if self.password != self.password_repeat:
            raise BadRequestException("Passwords do not match")
        return self


class RegisterRequest(BaseModel):
    payload: RegisterRequestPayload


class RegisterResponsePayload(BaseModel):
    worker_id: str
    email: Optional[str]
    role: Optional[str]
    first_name: Optional[str]
    middle_name: Optional[str]
    last_name: Optional[str]


class RegisterResponse(
    BaseResponse[RegisterResponsePayload, BaseResponseMeta]
):
    meta: BaseResponseMeta = BaseResponseMeta(
        status=ResponseStatus.OK,
        code="201",
        messages=[]
    )