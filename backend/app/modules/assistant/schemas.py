from pydantic import BaseModel, ConfigDict, Field, StrictInt

from ..inventory.inventory_count_schemas import InventoryCountLineUpdatePayload
from ..inventory.purchase_schemas import CreateStockTransferPayload


class AssistantInventoryCountUpdatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True)

    count_id: StrictInt = Field(alias="countId", gt=0)
    version: StrictInt = Field(gt=0)
    notes: str | None = Field(default=None, max_length=500)
    lines: list[InventoryCountLineUpdatePayload] = Field(min_length=1, max_length=500)


class AssistantStockTransferDraftPayload(CreateStockTransferPayload):
    """智能体调拨草稿，沿用手工调拨字段并保持严格校验。"""
