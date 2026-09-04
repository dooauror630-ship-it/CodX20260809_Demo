from datetime import date
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, field_validator, model_validator


class CustomerListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    farm_id: int = Field(alias="farmId", gt=0)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, alias="pageSize", ge=1, le=100)
    keyword: str = ""


class CreateCustomerPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
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


class SalesLinePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    item_id: StrictInt = Field(alias="itemId", gt=0)
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    unit_price: Decimal = Field(alias="unitPrice", ge=0, max_digits=16, decimal_places=4)


class CreateSalesOrderPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    farm_id: StrictInt = Field(alias="farmId", gt=0)
    order_no: StrictStr = Field(alias="orderNo", min_length=3, max_length=30, pattern=r"^[A-Za-z0-9_-]+$")
    customer_id: StrictInt = Field(alias="customerId", gt=0)
    warehouse_id: StrictInt = Field(alias="warehouseId", gt=0)
    sale_date: date = Field(alias="saleDate")
    lines: list[SalesLinePayload] = Field(min_length=1, max_length=100)
    notes: StrictStr | None = Field(default=None, max_length=500)

    @field_validator("order_no")
    @classmethod
    def normalize_no(cls, value):
        return value.upper()

    @model_validator(mode="after")
    def unique_items(self):
        if len({line.item_id for line in self.lines}) != len(self.lines):
            raise ValueError("duplicate item")
        return self


class SalesListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    farm_id: int = Field(alias="farmId", gt=0)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, alias="pageSize", ge=1, le=100)
    status: Literal["all", "DRAFT", "POSTED"] = "all"


class CreatePaymentPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    farm_id: StrictInt = Field(alias="farmId", gt=0)
    payment_no: StrictStr = Field(alias="paymentNo", min_length=3, max_length=30, pattern=r"^[A-Za-z0-9_-]+$")
    business_date: date = Field(alias="businessDate")
    amount: Decimal = Field(gt=0, max_digits=16, decimal_places=2)
    method: StrictStr = Field(min_length=2, max_length=20)
    customer_id: StrictInt | None = Field(default=None, alias="customerId", gt=0)
    sales_order_id: StrictInt | None = Field(default=None, alias="salesOrderId", gt=0)
    notes: StrictStr | None = Field(default=None, max_length=500)

    @field_validator("payment_no")
    @classmethod
    def normalize_no(cls, value):
        return value.upper()


class SalesReturnLinePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    sales_order_line_id: StrictInt = Field(alias="salesOrderLineId", gt=0)
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)


class CreateSalesReturnPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    farm_id: StrictInt = Field(alias="farmId", gt=0)
    return_no: StrictStr = Field(alias="returnNo", min_length=3, max_length=30, pattern=r"^[A-Za-z0-9_-]+$")
    sales_order_id: StrictInt = Field(alias="salesOrderId", gt=0)
    return_date: date = Field(alias="returnDate")
    lines: list[SalesReturnLinePayload] = Field(min_length=1, max_length=100)

    @field_validator("return_no")
    @classmethod
    def normalize_no(cls, value):
        return value.upper()
