from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, field_validator, model_validator


CropCycleStatus = Literal["PLANNED", "ACTIVE", "HARVESTING", "CLOSED", "CANCELLED"]
FieldOperationType = Literal[
    "LAND_PREPARATION", "SOWING", "TRANSPLANTING", "IRRIGATION", "FERTILIZATION",
    "PEST_CONTROL", "WEEDING", "OTHER",
]


class CropCycleListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    farm_id: int = Field(alias="farmId", gt=0)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, alias="pageSize", ge=1, le=100)
    keyword: str = Field(default="", max_length=100)
    status: Literal["all", "PLANNED", "ACTIVE", "HARVESTING", "CLOSED", "CANCELLED"] = "all"


class CreateCropCyclePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    farm_id: StrictInt = Field(alias="farmId", gt=0)
    cycle_code: StrictStr = Field(alias="cycleCode", min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    plot_id: StrictInt = Field(alias="plotId", gt=0)
    crop_type_id: StrictInt = Field(alias="cropTypeId", gt=0)
    variety_id: StrictInt = Field(alias="varietyId", gt=0)
    area_mu: Decimal = Field(alias="areaMu", gt=0, max_digits=14, decimal_places=3)
    planned_start_date: date = Field(alias="plannedStartDate")
    planned_end_date: date = Field(alias="plannedEndDate")
    notes: StrictStr | None = Field(default=None, max_length=500)

    @field_validator("cycle_code")
    @classmethod
    def normalize_code(cls, value):
        return value.upper()

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value):
        return value or None

    @model_validator(mode="after")
    def validate_planned_dates(self):
        if self.planned_end_date < self.planned_start_date:
            raise ValueError("planned end date before start")
        return self


class UpdateCropCycleStatusPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    status: CropCycleStatus
    actual_start_date: date | None = Field(default=None, alias="actualStartDate")
    actual_end_date: date | None = Field(default=None, alias="actualEndDate")

    @model_validator(mode="after")
    def validate_actual_dates(self):
        if self.actual_end_date is not None and self.actual_start_date is None:
            raise ValueError("actual start date required")
        if self.actual_start_date and self.actual_end_date and self.actual_end_date < self.actual_start_date:
            raise ValueError("actual end date before start")
        return self


class FieldOperationListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    farm_id: int = Field(alias="farmId", gt=0)
    crop_cycle_id: int = Field(alias="cropCycleId", gt=0)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, alias="pageSize", ge=1, le=100)


class CreateFieldOperationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    farm_id: StrictInt = Field(alias="farmId", gt=0)
    crop_cycle_id: StrictInt = Field(alias="cropCycleId", gt=0)
    operation_type: FieldOperationType = Field(alias="operationType")
    operation_date: date = Field(alias="operationDate")
    area_mu: Decimal = Field(alias="areaMu", gt=0, max_digits=14, decimal_places=3)
    labor_hours: Decimal = Field(default=Decimal("0"), alias="laborHours", ge=0, max_digits=12, decimal_places=2)
    machine_hours: Decimal = Field(default=Decimal("0"), alias="machineHours", ge=0, max_digits=12, decimal_places=2)
    labor_cost: Decimal = Field(default=Decimal("0"), alias="laborCost", ge=0, max_digits=16, decimal_places=2)
    service_cost: Decimal = Field(default=Decimal("0"), alias="serviceCost", ge=0, max_digits=16, decimal_places=2)
    notes: StrictStr | None = Field(default=None, max_length=500)

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value):
        return value or None


class FieldOperationInputListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    farm_id: int = Field(alias="farmId", gt=0)
    field_operation_id: int = Field(alias="fieldOperationId", gt=0)


class CreateFieldOperationInputPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    farm_id: StrictInt = Field(alias="farmId", gt=0)
    field_operation_id: StrictInt = Field(alias="fieldOperationId", gt=0)
    stock_document_id: StrictInt = Field(alias="stockDocumentId", gt=0)


class HarvestBatchListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)
    farm_id: int = Field(alias="farmId", gt=0)
    crop_cycle_id: int = Field(alias="cropCycleId", gt=0)


class CreateHarvestBatchPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)
    farm_id: StrictInt = Field(alias="farmId", gt=0)
    crop_cycle_id: StrictInt = Field(alias="cropCycleId", gt=0)
    harvest_no: StrictStr = Field(alias="harvestNo", min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    harvest_date: date = Field(alias="harvestDate")
    gross_weight: Decimal = Field(alias="grossWeight", gt=0, max_digits=14, decimal_places=3)
    net_weight: Decimal = Field(alias="netWeight", gt=0, max_digits=14, decimal_places=3)
    unit_id: StrictInt = Field(alias="unitId", gt=0)
    warehouse_id: StrictInt = Field(alias="warehouseId", gt=0)
    notes: StrictStr | None = Field(default=None, max_length=500)

    @field_validator("harvest_no")
    @classmethod
    def normalize_no(cls, value):
        return value.upper()

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value):
        return value or None

    @model_validator(mode="after")
    def validate_weights(self):
        if self.net_weight > self.gross_weight:
            raise ValueError("net weight exceeds gross weight")
        return self


class TobaccoCuringBatchListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)
    farm_id: int = Field(alias="farmId", gt=0)
    crop_cycle_id: int = Field(alias="cropCycleId", gt=0)


class CreateTobaccoCuringBatchPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)
    farm_id: StrictInt = Field(alias="farmId", gt=0)
    crop_cycle_id: StrictInt = Field(alias="cropCycleId", gt=0)
    curing_no: StrictStr = Field(alias="curingNo", min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    start_at: datetime = Field(alias="startAt")
    input_weight: Decimal = Field(alias="inputWeight", gt=0, max_digits=14, decimal_places=3)
    unit_id: StrictInt = Field(alias="unitId", gt=0)
    notes: StrictStr | None = Field(default=None, max_length=500)

    @field_validator("curing_no")
    @classmethod
    def normalize_no(cls, value):
        return value.upper()

    @field_validator("start_at")
    @classmethod
    def validate_local_time(cls, value):
        if value.tzinfo is not None:
            raise ValueError("timezone offset is not supported")
        return value

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value):
        return value or None


class CompleteTobaccoCuringBatchPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    end_at: datetime = Field(alias="endAt")
    output_weight: Decimal = Field(alias="outputWeight", gt=0, max_digits=14, decimal_places=3)
    fuel_cost: Decimal = Field(default=Decimal("0"), alias="fuelCost", ge=0, max_digits=16, decimal_places=2)
    electricity_cost: Decimal = Field(default=Decimal("0"), alias="electricityCost", ge=0, max_digits=16, decimal_places=2)

    @field_validator("end_at")
    @classmethod
    def validate_local_time(cls, value):
        if value.tzinfo is not None:
            raise ValueError("timezone offset is not supported")
        return value


class GradingRecordListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)
    farm_id: int = Field(alias="farmId", gt=0)
    harvest_batch_id: int = Field(alias="harvestBatchId", gt=0)


class CreateGradingRecordPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)
    farm_id: StrictInt = Field(alias="farmId", gt=0)
    harvest_batch_id: StrictInt = Field(alias="harvestBatchId", gt=0)
    grade_code: StrictStr = Field(alias="gradeCode", min_length=1, max_length=30, pattern=r"^[A-Za-z0-9_-]+$")
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    unit_price_reference: Decimal = Field(default=Decimal("0"), alias="unitPriceReference", ge=0, max_digits=16, decimal_places=4)
    notes: StrictStr | None = Field(default=None, max_length=500)

    @field_validator("grade_code")
    @classmethod
    def normalize_grade(cls, value):
        return value.upper()

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value):
        return value or None
