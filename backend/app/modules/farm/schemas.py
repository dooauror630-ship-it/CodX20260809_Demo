from decimal import Decimal
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)


FarmRole = Literal["manager", "operator", "viewer"]
BarnType = Literal["pig", "chicken", "isolation", "other"]


class FarmListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, alias="pageSize", ge=1, le=100)
    keyword: str = Field(default="", max_length=80)
    status: Literal["all", "active", "disabled"] = "all"


class CreateFarmPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    code: StrictStr = Field(min_length=2, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    name: StrictStr = Field(min_length=2, max_length=80)
    owner_name: StrictStr = Field(alias="ownerName", min_length=2, max_length=40)
    address: StrictStr | None = Field(default=None, max_length=255)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value):
        return value.upper()

    @field_validator("address")
    @classmethod
    def normalize_address(cls, value):
        return value or None


class UpdateFarmPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    code: StrictStr | None = Field(default=None, min_length=2, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    name: StrictStr | None = Field(default=None, min_length=2, max_length=80)
    owner_name: StrictStr | None = Field(default=None, alias="ownerName", min_length=2, max_length=40)
    address: StrictStr | None = Field(default=None, max_length=255)
    is_active: StrictBool | None = Field(default=None, alias="isActive")

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value):
        return value.upper() if value else value

    @field_validator("address")
    @classmethod
    def normalize_address(cls, value):
        return value or None

    @model_validator(mode="after")
    def validate_changes(self):
        if not self.model_fields_set:
            raise ValueError("no changes")
        for field in ("code", "name", "owner_name", "is_active"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class CreateFarmMemberPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    user_id: int = Field(alias="userId", gt=0)
    role_code: FarmRole = Field(alias="roleCode")


class UpdateFarmMemberPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    role_code: FarmRole | None = Field(default=None, alias="roleCode")
    is_active: StrictBool | None = Field(default=None, alias="isActive")

    @model_validator(mode="after")
    def validate_changes(self):
        if self.role_code is None and self.is_active is None:
            raise ValueError("no changes")
        return self


class FarmResourceListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    farm_id: int = Field(alias="farmId", gt=0)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, alias="pageSize", ge=1, le=100)
    keyword: str = Field(default="", max_length=80)
    status: Literal["all", "active", "disabled"] = "all"


class CreateBarnPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    farm_id: StrictInt = Field(alias="farmId", gt=0)
    code: StrictStr = Field(min_length=2, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    name: StrictStr = Field(min_length=2, max_length=80)
    barn_type: BarnType = Field(alias="barnType")
    capacity: StrictInt = Field(ge=0, le=2_000_000_000)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value):
        return value.upper()


class UpdateBarnPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    code: StrictStr | None = Field(default=None, min_length=2, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    name: StrictStr | None = Field(default=None, min_length=2, max_length=80)
    barn_type: BarnType | None = Field(default=None, alias="barnType")
    capacity: StrictInt | None = Field(default=None, ge=0, le=2_000_000_000)
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


class CreatePlotPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    farm_id: StrictInt = Field(alias="farmId", gt=0)
    code: StrictStr = Field(min_length=2, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    name: StrictStr = Field(min_length=2, max_length=80)
    area_mu: Decimal = Field(alias="areaMu", gt=0, max_digits=14, decimal_places=3)
    soil_type: StrictStr | None = Field(default=None, alias="soilType", max_length=40)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value):
        return value.upper()

    @field_validator("soil_type")
    @classmethod
    def normalize_soil_type(cls, value):
        return value or None


class UpdatePlotPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    code: StrictStr | None = Field(default=None, min_length=2, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    name: StrictStr | None = Field(default=None, min_length=2, max_length=80)
    area_mu: Decimal | None = Field(default=None, alias="areaMu", gt=0, max_digits=14, decimal_places=3)
    soil_type: StrictStr | None = Field(default=None, alias="soilType", max_length=40)
    is_active: StrictBool | None = Field(default=None, alias="isActive")

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value):
        return value.upper() if value else value

    @field_validator("soil_type")
    @classmethod
    def normalize_soil_type(cls, value):
        return value or None

    @model_validator(mode="after")
    def validate_changes(self):
        if not self.model_fields_set:
            raise ValueError("no changes")
        for field in ("code", "name", "area_mu", "is_active"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self
