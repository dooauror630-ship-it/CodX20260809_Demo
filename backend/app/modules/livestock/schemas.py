from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, field_validator, model_validator


LivestockBatchStatus = Literal["all", "ACTIVE", "CLOSED"]
LivestockMovementType = Literal["TRANSFER", "DEATH", "CULL", "EXIT"]
LivestockHealthType = Literal["VACCINATION", "MEDICATION", "DISEASE", "OTHER"]
LivestockCostType = Literal["ENTRY", "LABOR", "OVERHEAD", "OTHER"]
SupportedLivestockSpecies = Literal["PIG", "CHICKEN"]


class LivestockBatchListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    farm_id: int = Field(alias="farmId", gt=0)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, alias="pageSize", ge=1, le=100)
    keyword: str = Field(default="", max_length=100)
    status: LivestockBatchStatus = "all"
    species_code: SupportedLivestockSpecies = Field(default="PIG", alias="speciesCode")


class LivestockAnalysisQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    farm_id: int = Field(alias="farmId", gt=0)
    trend_days: int = Field(default=30, alias="trendDays", ge=7, le=90)
    species_code: SupportedLivestockSpecies = Field(default="PIG", alias="speciesCode")


class CreateLivestockBatchPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    farm_id: StrictInt = Field(alias="farmId", gt=0)
    species_id: StrictInt = Field(alias="speciesId", gt=0)
    batch_no: StrictStr = Field(
        alias="batchNo", min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_-]+$"
    )
    name: StrictStr = Field(min_length=2, max_length=80)
    entry_no: StrictStr = Field(
        alias="entryNo", min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_-]+$"
    )
    entry_date: date = Field(alias="entryDate")
    barn_id: StrictInt = Field(alias="barnId", gt=0)
    initial_count: StrictInt = Field(alias="initialCount", gt=0, le=2_000_000_000)
    source: StrictStr | None = Field(default=None, max_length=120)
    notes: StrictStr | None = Field(default=None, max_length=500)

    @field_validator("batch_no", "entry_no")
    @classmethod
    def normalize_numbers(cls, value):
        return value.upper()

    @field_validator("source", "notes")
    @classmethod
    def normalize_optional_text(cls, value):
        return value or None


class CreateLivestockMovementPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    farm_id: StrictInt = Field(alias="farmId", gt=0)
    batch_id: StrictInt = Field(alias="batchId", gt=0)
    movement_no: StrictStr = Field(
        alias="movementNo", min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_-]+$"
    )
    movement_type: LivestockMovementType = Field(alias="movementType")
    occurred_on: date = Field(alias="occurredOn")
    from_barn_id: StrictInt | None = Field(default=None, alias="fromBarnId", gt=0)
    to_barn_id: StrictInt | None = Field(default=None, alias="toBarnId", gt=0)
    quantity: StrictInt = Field(gt=0, le=2_000_000_000)
    reason: StrictStr | None = Field(default=None, max_length=255)
    notes: StrictStr | None = Field(default=None, max_length=500)

    @field_validator("movement_no")
    @classmethod
    def normalize_movement_no(cls, value):
        return value.upper()

    @field_validator("reason", "notes")
    @classmethod
    def normalize_optional_text(cls, value):
        return value or None

    @model_validator(mode="after")
    def validate_barns_and_reason(self):
        if self.movement_type == "TRANSFER":
            if not self.from_barn_id or not self.to_barn_id or self.from_barn_id == self.to_barn_id:
                raise ValueError("transfer barns invalid")
        elif not self.from_barn_id or self.to_barn_id is not None:
            raise ValueError("outbound barn invalid")
        if self.movement_type in ("DEATH", "CULL") and not self.reason:
            raise ValueError("reason required")
        return self


class CreateLivestockHealthRecordPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    farm_id: StrictInt = Field(alias="farmId", gt=0)
    batch_id: StrictInt = Field(alias="batchId", gt=0)
    record_no: StrictStr = Field(alias="recordNo", min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    record_type: LivestockHealthType = Field(alias="recordType")
    occurred_on: date = Field(alias="occurredOn")
    description: StrictStr = Field(min_length=2, max_length=255)
    medicine_name: StrictStr | None = Field(default=None, alias="medicineName", max_length=120)
    dosage: StrictStr | None = Field(default=None, max_length=80)
    notes: StrictStr | None = Field(default=None, max_length=500)

    @field_validator("record_no")
    @classmethod
    def normalize_record_no(cls, value):
        return value.upper()

    @field_validator("medicine_name", "dosage", "notes")
    @classmethod
    def normalize_optional_text(cls, value):
        return value or None


class CreateLivestockWeightRecordPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    farm_id: StrictInt = Field(alias="farmId", gt=0)
    batch_id: StrictInt = Field(alias="batchId", gt=0)
    record_no: StrictStr = Field(alias="recordNo", min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    occurred_on: date = Field(alias="occurredOn")
    sample_count: StrictInt = Field(alias="sampleCount", gt=0, le=2_000_000_000)
    average_weight: Decimal = Field(alias="averageWeight", gt=0, max_digits=10, decimal_places=3)
    notes: StrictStr | None = Field(default=None, max_length=500)

    @field_validator("record_no")
    @classmethod
    def normalize_record_no(cls, value):
        return value.upper()

    @field_validator("notes")
    @classmethod
    def normalize_optional_text(cls, value):
        return value or None


class CreateLivestockCostEntryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    farm_id: StrictInt = Field(alias="farmId", gt=0)
    batch_id: StrictInt = Field(alias="batchId", gt=0)
    entry_no: StrictStr = Field(alias="entryNo", min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    business_date: date = Field(alias="businessDate")
    cost_type: LivestockCostType = Field(alias="costType")
    amount: Decimal = Field(gt=0, max_digits=16, decimal_places=2)
    description: StrictStr = Field(min_length=2, max_length=255)
    notes: StrictStr | None = Field(default=None, max_length=500)

    @field_validator("entry_no")
    @classmethod
    def normalize_entry_no(cls, value):
        return value.upper()

    @field_validator("notes")
    @classmethod
    def normalize_cost_notes(cls, value):
        return value or None
