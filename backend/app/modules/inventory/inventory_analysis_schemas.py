from pydantic import BaseModel, ConfigDict, Field


class InventoryAnalysisQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    farm_id: int = Field(alias="farmId", gt=0)
    warehouse_id: int | None = Field(default=None, alias="warehouseId", gt=0)
    expiry_days: int = Field(default=30, alias="expiryDays", ge=1, le=365)
    trend_days: int = Field(default=30, alias="trendDays", ge=7, le=90)
