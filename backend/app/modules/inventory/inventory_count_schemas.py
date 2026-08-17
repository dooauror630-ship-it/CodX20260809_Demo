from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, field_validator, model_validator


InventoryCountStatus = Literal["all", "DRAFT", "POSTED", "CANCELLED"]


class InventoryCountListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    farm_id: int = Field(alias="farmId", gt=0)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, alias="pageSize", ge=1, le=100)
    keyword: str = Field(default="", max_length=100)
    status: InventoryCountStatus = "all"
    date_from: date | None = Field(default=None, alias="dateFrom")
    date_to: date | None = Field(default=None, alias="dateTo")

    @model_validator(mode="after")
    def validate_dates(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("invalid date range")
        return self


class CreateInventoryCountPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    farm_id: StrictInt = Field(alias="farmId", gt=0)
    count_no: StrictStr = Field(
        alias="countNo",
        min_length=3,
        max_length=40,
        pattern=r"^[A-Za-z0-9_-]+$",
    )
    warehouse_id: StrictInt = Field(alias="warehouseId", gt=0)
    count_date: date = Field(alias="countDate")
    notes: StrictStr | None = Field(default=None, max_length=500)

    @field_validator("count_no")
    @classmethod
    def normalize_count_no(cls, value):
        return value.upper()

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value):
        return value or None


class InventoryCountLineUpdatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    id: StrictInt = Field(gt=0)
    actual_quantity: Decimal = Field(alias="actualQuantity", ge=0, max_digits=14, decimal_places=3)
    reason: StrictStr | None = Field(default=None, max_length=255)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value):
        return value or None


class UpdateInventoryCountPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    version: StrictInt = Field(gt=0)
    notes: StrictStr | None = Field(default=None, max_length=500)
    lines: list[InventoryCountLineUpdatePayload] = Field(min_length=1, max_length=500)

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value):
        return value or None

    @model_validator(mode="after")
    def validate_lines(self):
        ids = [line.id for line in self.lines]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate count line")
        return self


class InventoryCountActionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: StrictInt = Field(gt=0)
