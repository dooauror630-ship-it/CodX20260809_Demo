from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr, field_validator, model_validator


class CreateCropVarietyPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    crop_type_id: StrictInt = Field(alias="cropTypeId", gt=0)
    code: StrictStr = Field(min_length=2, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    name: StrictStr = Field(min_length=1, max_length=80)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value):
        return value.upper()


class UpdateCropVarietyPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    crop_type_id: StrictInt | None = Field(default=None, alias="cropTypeId", gt=0)
    code: StrictStr | None = Field(default=None, min_length=2, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    name: StrictStr | None = Field(default=None, min_length=1, max_length=80)
    is_active: StrictBool | None = Field(default=None, alias="isActive")

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value):
        return value.upper() if value else value

    @model_validator(mode="after")
    def validate_changes(self):
        if not self.model_fields_set:
            raise ValueError("no changes")
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self
