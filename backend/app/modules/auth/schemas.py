import re

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr, ValidationError, field_validator

from ...core.errors import ApiError


USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]{4,20}$")


def validate_password_strength(value):
    if not 8 <= len(value) <= 64 or not any(ch.isalpha() for ch in value) or not any(ch.isdigit() for ch in value):
        raise ValueError("invalid password")
    return value


class RegisterPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    username: StrictStr
    display_name: StrictStr = Field(alias="displayName")
    password: StrictStr

    @field_validator("username")
    @classmethod
    def validate_username(cls, value):
        if not USERNAME_PATTERN.fullmatch(value):
            raise ValueError("invalid username")
        return value

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value):
        if not 2 <= len(value) <= 20:
            raise ValueError("invalid display name")
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value):
        return validate_password_strength(value)


class LoginPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    username: StrictStr
    password: StrictStr
    remember: StrictBool = False

    @field_validator("username", "password")
    @classmethod
    def validate_required(cls, value):
        if not value:
            raise ValueError("required")
        return value


REGISTER_FIELD_MESSAGES = {
    "username": "账号须为 4-20 位字母、数字或下划线",
    "displayName": "姓名须为 2-20 个字符",
    "password": "密码须为 8-64 位，且同时包含字母和数字",
}


def parse_payload(model_type, data, generic_message, field_messages=None):
    if not isinstance(data, dict):
        raise ApiError("请求数据格式错误", 400, "PAYLOAD_INVALID")
    try:
        return model_type.model_validate(data)
    except ValidationError as error:
        first_error = error.errors()[0]
        location = first_error.get("loc", ())
        field = str(location[0]) if location else None
        if field == "display_name":
            field = "displayName"
        known_fields = field_messages or {}
        message = known_fields.get(field, generic_message)
        raise ApiError(message, 400, "VALIDATION_ERROR", field if field in known_fields else None) from error
