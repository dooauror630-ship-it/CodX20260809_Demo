from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr, field_validator, model_validator

from ..auth.schemas import validate_password_strength


UserRole = Literal["admin", "operator"]


class UserListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, alias="pageSize", ge=1, le=100)
    keyword: str = Field(default="", max_length=50)
    role: UserRole | None = None
    status: Literal["all", "active", "disabled"] = "all"


class UpdateUserPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    display_name: StrictStr | None = Field(default=None, alias="displayName")
    role: UserRole | None = None
    is_active: StrictBool | None = Field(default=None, alias="isActive")

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value):
        if value is not None and not 2 <= len(value) <= 20:
            raise ValueError("invalid display name")
        return value

    @model_validator(mode="after")
    def validate_changes(self):
        if self.display_name is None and self.role is None and self.is_active is None:
            raise ValueError("no changes")
        return self


class ResetPasswordPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    password: StrictStr

    @field_validator("password")
    @classmethod
    def validate_password(cls, value):
        return validate_password_strength(value)
