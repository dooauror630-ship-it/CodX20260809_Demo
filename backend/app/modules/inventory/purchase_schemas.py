from datetime import date
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


PurchaseStatus = Literal["all", "DRAFT", "POSTED", "CANCELLED"]


class SupplierListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    farm_id: int = Field(alias="farmId", gt=0)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, alias="pageSize", ge=1, le=100)
    keyword: str = Field(default="", max_length=100)
    status: Literal["all", "active", "disabled"] = "all"


class CreateSupplierPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    farm_id: StrictInt = Field(alias="farmId", gt=0)
    code: StrictStr = Field(min_length=2, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    name: StrictStr = Field(min_length=2, max_length=100)
    contact: StrictStr | None = Field(default=None, max_length=40)
    phone: StrictStr | None = Field(default=None, max_length=30)
    address: StrictStr | None = Field(default=None, max_length=255)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value):
        return value.upper()

    @field_validator("contact", "phone", "address")
    @classmethod
    def normalize_optional_text(cls, value):
        return value or None


class UpdateSupplierPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    code: StrictStr | None = Field(default=None, min_length=2, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    name: StrictStr | None = Field(default=None, min_length=2, max_length=100)
    contact: StrictStr | None = Field(default=None, max_length=40)
    phone: StrictStr | None = Field(default=None, max_length=30)
    address: StrictStr | None = Field(default=None, max_length=255)
    is_active: StrictBool | None = Field(default=None, alias="isActive")

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value):
        return value.upper() if value else value

    @field_validator("contact", "phone", "address")
    @classmethod
    def normalize_optional_text(cls, value):
        return value or None

    @model_validator(mode="after")
    def validate_changes(self):
        if not self.model_fields_set:
            raise ValueError("no changes")
        for field in ("code", "name", "is_active"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class PurchaseLinePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    item_id: StrictInt = Field(alias="itemId", gt=0)
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    unit_price: Decimal = Field(alias="unitPrice", ge=0, max_digits=16, decimal_places=4)
    lot_no: StrictStr | None = Field(default=None, alias="lotNo", max_length=64)
    expires_on: date | None = Field(default=None, alias="expiresOn")

    @field_validator("lot_no")
    @classmethod
    def normalize_lot_no(cls, value):
        return value or None


class CreatePurchasePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    farm_id: StrictInt = Field(alias="farmId", gt=0)
    order_no: StrictStr = Field(alias="orderNo", min_length=3, max_length=30, pattern=r"^[A-Za-z0-9_-]+$")
    supplier_id: StrictInt = Field(alias="supplierId", gt=0)
    warehouse_id: StrictInt = Field(alias="warehouseId", gt=0)
    order_date: date = Field(alias="orderDate")
    notes: StrictStr | None = Field(default=None, max_length=500)
    lines: list[PurchaseLinePayload] = Field(min_length=1, max_length=100)

    @field_validator("order_no")
    @classmethod
    def normalize_order_no(cls, value):
        return value.upper()

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value):
        return value or None

    @model_validator(mode="after")
    def validate_lines(self):
        keys = [(line.item_id, line.lot_no or "") for line in self.lines]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate item lot")
        if any(line.expires_on and line.expires_on < self.order_date for line in self.lines):
            raise ValueError("expiry before order date")
        return self


class UpdatePurchasePayload(CreatePurchasePayload):
    version: StrictInt = Field(gt=0)


class PurchaseActionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: StrictInt = Field(gt=0)


class CreatePurchaseReturnPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    farm_id: StrictInt = Field(alias="farmId", gt=0)
    document_no: StrictStr = Field(
        alias="documentNo",
        min_length=3,
        max_length=40,
        pattern=r"^[A-Za-z0-9_-]+$",
    )
    purchase_id: StrictInt = Field(alias="purchaseId", gt=0)
    purchase_line_id: StrictInt = Field(alias="purchaseLineId", gt=0)
    return_date: date = Field(alias="returnDate")
    warehouse_id: StrictInt = Field(alias="warehouseId", gt=0)
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)

    @field_validator("document_no")
    @classmethod
    def normalize_document_no(cls, value):
        return value.upper()


class CreateStockTransferPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    farm_id: StrictInt = Field(alias="farmId", gt=0)
    document_no: StrictStr = Field(
        alias="documentNo",
        min_length=3,
        max_length=40,
        pattern=r"^[A-Za-z0-9_-]+$",
    )
    from_warehouse_id: StrictInt = Field(alias="fromWarehouseId", gt=0)
    to_warehouse_id: StrictInt = Field(alias="toWarehouseId", gt=0)
    transfer_date: date = Field(alias="transferDate")
    item_id: StrictInt = Field(alias="itemId", gt=0)
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    lot_no: StrictStr | None = Field(default=None, alias="lotNo", max_length=64)

    @field_validator("document_no")
    @classmethod
    def normalize_document_no(cls, value):
        return value.upper()

    @field_validator("lot_no")
    @classmethod
    def normalize_transfer_lot(cls, value):
        return value or None

    @model_validator(mode="after")
    def validate_warehouses(self):
        if self.from_warehouse_id == self.to_warehouse_id:
            raise ValueError("warehouses must differ")
        return self


class CreateProductionStockOperationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    farm_id: StrictInt = Field(alias="farmId", gt=0)
    document_no: StrictStr = Field(
        alias="documentNo",
        min_length=3,
        max_length=40,
        pattern=r"^[A-Za-z0-9_-]+$",
    )
    operation_type: Literal["issue", "return"] = Field(alias="operationType")
    operation_date: date = Field(alias="operationDate")
    warehouse_id: StrictInt = Field(alias="warehouseId", gt=0)
    item_id: StrictInt = Field(alias="itemId", gt=0)
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    lot_no: StrictStr | None = Field(default=None, alias="lotNo", max_length=64)
    cost_object_type: Literal["farm", "barn", "plot"] = Field(alias="costObjectType")
    cost_object_id: StrictInt | None = Field(default=None, alias="costObjectId", gt=0)

    @field_validator("document_no")
    @classmethod
    def normalize_document_no(cls, value):
        return value.upper()

    @field_validator("lot_no")
    @classmethod
    def normalize_lot_no(cls, value):
        return value or None

    @model_validator(mode="after")
    def validate_cost_object(self):
        if self.cost_object_type == "farm" and self.cost_object_id is not None:
            raise ValueError("farm cost object must not have an id")
        if self.cost_object_type != "farm" and self.cost_object_id is None:
            raise ValueError("cost object id required")
        return self


class PurchaseListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    farm_id: int = Field(alias="farmId", gt=0)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, alias="pageSize", ge=1, le=100)
    keyword: str = Field(default="", max_length=100)
    status: PurchaseStatus = "all"
    date_from: date | None = Field(default=None, alias="dateFrom")
    date_to: date | None = Field(default=None, alias="dateTo")

    @model_validator(mode="after")
    def validate_dates(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("invalid date range")
        return self


class StockListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    farm_id: int = Field(alias="farmId", gt=0)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, alias="pageSize", ge=1, le=100)
    keyword: str = Field(default="", max_length=100)
    warehouse_id: int | None = Field(default=None, alias="warehouseId", gt=0)
    low_stock: bool = Field(default=False, alias="lowStock")


class StockLedgerQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    farm_id: int = Field(alias="farmId", gt=0)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, alias="pageSize", ge=1, le=100)
    keyword: str = Field(default="", max_length=100)
    warehouse_id: int | None = Field(default=None, alias="warehouseId", gt=0)
    item_id: int | None = Field(default=None, alias="itemId", gt=0)
    date_from: date | None = Field(default=None, alias="dateFrom")
    date_to: date | None = Field(default=None, alias="dateTo")

    @model_validator(mode="after")
    def validate_dates(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("invalid date range")
        return self
