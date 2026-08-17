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


StatusFilter = Literal["all", "active", "disabled"]
ItemType = Literal["feed", "veterinary_drug", "seed", "fertilizer", "pesticide", "product", "supply", "other"]


class WarehouseListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    farm_id: int = Field(alias="farmId", gt=0)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, alias="pageSize", ge=1, le=100)
    keyword: str = Field(default="", max_length=80)
    status: StatusFilter = "all"


class CreateWarehousePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    farm_id: StrictInt = Field(alias="farmId", gt=0)
    code: StrictStr = Field(min_length=2, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    name: StrictStr = Field(min_length=2, max_length=80)
    location: StrictStr | None = Field(default=None, max_length=255)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value):
        return value.upper()

    @field_validator("location")
    @classmethod
    def normalize_location(cls, value):
        return value or None


class UpdateWarehousePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    code: StrictStr | None = Field(default=None, min_length=2, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    name: StrictStr | None = Field(default=None, min_length=2, max_length=80)
    location: StrictStr | None = Field(default=None, max_length=255)
    is_active: StrictBool | None = Field(default=None, alias="isActive")

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value):
        return value.upper() if value else value

    @field_validator("location")
    @classmethod
    def normalize_location(cls, value):
        return value or None

    @model_validator(mode="after")
    def validate_changes(self):
        if not self.model_fields_set:
            raise ValueError("no changes")
        for field in ("code", "name", "is_active"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class CategoryListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    farm_id: int = Field(alias="farmId", gt=0)
    keyword: str = Field(default="", max_length=80)
    status: StatusFilter = "all"


class CreateCategoryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    farm_id: StrictInt = Field(alias="farmId", gt=0)
    parent_id: StrictInt | None = Field(default=None, alias="parentId", gt=0)
    code: StrictStr = Field(min_length=2, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    name: StrictStr = Field(min_length=1, max_length=80)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value):
        return value.upper()


class UpdateCategoryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    parent_id: StrictInt | None = Field(default=None, alias="parentId", gt=0)
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
        for field in ("code", "name", "is_active"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class ItemListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    farm_id: int = Field(alias="farmId", gt=0)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, alias="pageSize", ge=1, le=100)
    keyword: str = Field(default="", max_length=100)
    status: StatusFilter = "all"
    category_id: int | None = Field(default=None, alias="categoryId", gt=0)


class CreateItemPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    farm_id: StrictInt = Field(alias="farmId", gt=0)
    category_id: StrictInt = Field(alias="categoryId", gt=0)
    unit_id: StrictInt = Field(alias="unitId", gt=0)
    code: StrictStr = Field(min_length=2, max_length=30, pattern=r"^[A-Za-z0-9_-]+$")
    name: StrictStr = Field(min_length=1, max_length=100)
    item_type: ItemType = Field(alias="itemType")
    safety_stock: Decimal = Field(default=Decimal("0"), alias="safetyStock", ge=0, max_digits=14, decimal_places=3)
    lot_tracking: StrictBool = Field(default=False, alias="lotTracking")

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value):
        return value.upper()


class UpdateItemPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    category_id: StrictInt | None = Field(default=None, alias="categoryId", gt=0)
    unit_id: StrictInt | None = Field(default=None, alias="unitId", gt=0)
    code: StrictStr | None = Field(default=None, min_length=2, max_length=30, pattern=r"^[A-Za-z0-9_-]+$")
    name: StrictStr | None = Field(default=None, min_length=1, max_length=100)
    item_type: ItemType | None = Field(default=None, alias="itemType")
    safety_stock: Decimal | None = Field(default=None, alias="safetyStock", ge=0, max_digits=14, decimal_places=3)
    lot_tracking: StrictBool | None = Field(default=None, alias="lotTracking")
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
