from decimal import Decimal

from flask import current_app
from sqlalchemy import select

from ...core.errors import ApiError
from ...extensions import db
from ..catalog.models import LivestockSpecies, Unit
from ..farm.models import Farm
from ..inventory.models import InventoryBalance, Item, Warehouse
from ..inventory.purchase_service import _money_text, _stock_payload
from ..livestock.models import LivestockBatch, LivestockHealthRecord, LivestockWeightRecord
from ..livestock.service import (
    _batch_payload,
    _batch_states,
    _farm_summary,
    _health_payload,
    _weight_payload,
)


def _active_farm(farm_id):
    farm = db.session.get(Farm, farm_id)
    allowed_code = current_app.config.get("AGENT_FARM_CODE", "")
    if farm is None or (allowed_code and farm.code != allowed_code):
        raise ApiError("农场不存在", 404, "FARM_NOT_FOUND")
    if not farm.is_active:
        raise ApiError("农场已停用", 409, "FARM_DISABLED")
    return farm


def _farm_payload(farm):
    return {
        "id": farm.id,
        "code": farm.code,
        "name": farm.name,
        "ownerName": farm.owner_name,
        "address": farm.address,
        "timezone": farm.timezone,
    }


def list_farms():
    allowed_code = current_app.config.get("AGENT_FARM_CODE", "")
    conditions = [Farm.is_active.is_(True)]
    if allowed_code:
        conditions.append(Farm.code == allowed_code)
    farms = db.session.scalars(
        select(Farm).where(*conditions).order_by(Farm.name, Farm.id)
    ).all()
    return {"farms": [_farm_payload(farm) for farm in farms], "count": len(farms)}


def inventory_summary(farm_id):
    farm = _active_farm(farm_id)
    rows = db.session.execute(
        select(InventoryBalance, Item, Unit, Warehouse)
        .join(Item, Item.id == InventoryBalance.item_id)
        .join(Unit, Unit.id == Item.unit_id)
        .join(Warehouse, Warehouse.id == InventoryBalance.warehouse_id)
        .where(InventoryBalance.farm_id == farm_id)
        .order_by(Warehouse.name, Item.name, Item.id)
    ).all()
    stocks = [_stock_payload(*row) for row in rows]
    low_stock_items = [stock for stock in stocks if stock["lowStock"]]
    total_value = sum(
        (balance.quantity * balance.average_cost for balance, _item, _unit, _warehouse in rows),
        Decimal("0"),
    )
    return {
        "farm": _farm_payload(farm),
        "summary": {
            "stockItemCount": len(stocks),
            "lowStockCount": len(low_stock_items),
            "totalInventoryValue": _money_text(total_value),
        },
        "lowStockItems": low_stock_items[:20],
    }


def livestock_summary(farm_id):
    farm = _active_farm(farm_id)
    rows = db.session.execute(
        select(LivestockBatch, LivestockSpecies)
        .join(LivestockSpecies, LivestockSpecies.id == LivestockBatch.species_id)
        .where(LivestockBatch.farm_id == farm_id, LivestockBatch.status == "ACTIVE")
        .order_by(LivestockBatch.entry_date.desc(), LivestockBatch.id.desc())
        .limit(20)
    ).all()
    states = _batch_states([batch.id for batch, _species in rows])
    health_records = db.session.scalars(
        select(LivestockHealthRecord)
        .where(LivestockHealthRecord.farm_id == farm_id)
        .order_by(LivestockHealthRecord.occurred_on.desc(), LivestockHealthRecord.id.desc())
        .limit(10)
    ).all()
    weight_records = db.session.scalars(
        select(LivestockWeightRecord)
        .where(LivestockWeightRecord.farm_id == farm_id)
        .order_by(LivestockWeightRecord.occurred_on.desc(), LivestockWeightRecord.id.desc())
        .limit(10)
    ).all()
    return {
        "farm": _farm_payload(farm),
        "summary": _farm_summary(farm_id),
        "activeBatches": [
            _batch_payload(batch, species, states[batch.id]) for batch, species in rows
        ],
        "recentHealthRecords": [_health_payload(record) for record in health_records],
        "recentWeightRecords": [_weight_payload(record) for record in weight_records],
    }
