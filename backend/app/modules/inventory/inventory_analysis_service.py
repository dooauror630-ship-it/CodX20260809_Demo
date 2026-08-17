from datetime import datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import case, func, select

from ...extensions import db
from ..catalog.models import Unit
from ..farm.service import get_accessible_farm
from .models import Item, StockDocument, StockMovementLine, Warehouse
from .purchase_service import _money_text, _number_text


def _decimal(value):
    return value if isinstance(value, Decimal) else Decimal(str(value or 0))


def inventory_analysis(query, actor, today=None):
    get_accessible_farm(query.farm_id, actor)
    today = today or datetime.now().date()
    warehouse_condition = (
        [StockMovementLine.warehouse_id == query.warehouse_id]
        if query.warehouse_id
        else []
    )

    lot_quantity = func.sum(StockMovementLine.quantity_delta)
    lot_expiry = func.max(StockMovementLine.expires_on)
    expiry_rows = db.session.execute(
        select(
            Warehouse.id,
            Warehouse.name,
            Item.id,
            Item.code,
            Item.name,
            Unit.name,
            StockMovementLine.lot_no,
            lot_expiry,
            lot_quantity,
        )
        .join(StockDocument, StockDocument.id == StockMovementLine.stock_document_id)
        .join(Warehouse, Warehouse.id == StockMovementLine.warehouse_id)
        .join(Item, Item.id == StockMovementLine.item_id)
        .join(Unit, Unit.id == Item.unit_id)
        .where(
            StockDocument.farm_id == query.farm_id,
            StockDocument.status == "POSTED",
            StockMovementLine.expires_on.is_not(None),
            *warehouse_condition,
        )
        .group_by(
            Warehouse.id,
            Warehouse.name,
            Item.id,
            Item.code,
            Item.name,
            Unit.name,
            StockMovementLine.lot_no,
        )
        .having(
            lot_quantity > 0,
            lot_expiry <= today + timedelta(days=query.expiry_days),
        )
        .order_by(lot_expiry, Warehouse.name, Item.name, StockMovementLine.lot_no)
    ).all()

    expiry_lots = []
    expired_count = 0
    for row in expiry_rows:
        days_remaining = (row[7] - today).days
        status = "EXPIRED" if days_remaining < 0 else "EXPIRING"
        expired_count += status == "EXPIRED"
        expiry_lots.append({
            "warehouseId": row[0],
            "warehouseName": row[1],
            "itemId": row[2],
            "itemCode": row[3],
            "itemName": row[4],
            "unitName": row[5],
            "lotNo": row[6],
            "expiresOn": row[7].isoformat(),
            "quantity": _number_text(_decimal(row[8])),
            "daysRemaining": days_remaining,
            "status": status,
        })

    start_date = today - timedelta(days=query.trend_days - 1)
    movement_date = func.date(StockDocument.occurred_at)
    inbound_amount = func.sum(case(
        (StockMovementLine.quantity_delta > 0, StockMovementLine.quantity_delta * StockMovementLine.unit_cost),
        else_=0,
    ))
    outbound_amount = func.sum(case(
        (StockMovementLine.quantity_delta < 0, StockMovementLine.quantity_delta * StockMovementLine.unit_cost * -1),
        else_=0,
    ))
    trend_rows = db.session.execute(
        select(movement_date, inbound_amount, outbound_amount)
        .join(StockDocument, StockDocument.id == StockMovementLine.stock_document_id)
        .where(
            StockDocument.farm_id == query.farm_id,
            StockDocument.status == "POSTED",
            StockDocument.occurred_at >= datetime.combine(start_date, time.min),
            *warehouse_condition,
        )
        .group_by(movement_date)
        .order_by(movement_date)
    ).all()
    trend_by_date = {
        (value.isoformat() if hasattr(value, "isoformat") else str(value)): (
            _decimal(inbound),
            _decimal(outbound),
        )
        for value, inbound, outbound in trend_rows
    }
    trend = []
    period_inbound = Decimal("0")
    period_outbound = Decimal("0")
    for offset in range(query.trend_days):
        value = start_date + timedelta(days=offset)
        inbound, outbound = trend_by_date.get(value.isoformat(), (Decimal("0"), Decimal("0")))
        period_inbound += inbound
        period_outbound += outbound
        trend.append({
            "date": value.isoformat(),
            "inboundAmount": _money_text(inbound),
            "outboundAmount": _money_text(outbound),
        })

    net_quantity = func.sum(StockMovementLine.quantity_delta * -1)
    net_amount = func.sum(StockMovementLine.quantity_delta * StockMovementLine.unit_cost * -1)
    consumed_rows = db.session.execute(
        select(
            Item.id,
            Item.code,
            Item.name,
            Unit.name,
            net_quantity,
            net_amount,
        )
        .join(StockDocument, StockDocument.id == StockMovementLine.stock_document_id)
        .join(Item, Item.id == StockMovementLine.item_id)
        .join(Unit, Unit.id == Item.unit_id)
        .where(
            StockDocument.farm_id == query.farm_id,
            StockDocument.status == "POSTED",
            StockDocument.document_type.in_(("PRODUCTION_ISSUE", "PRODUCTION_RETURN")),
            StockDocument.occurred_at >= datetime.combine(start_date, time.min),
            *warehouse_condition,
        )
        .group_by(Item.id, Item.code, Item.name, Unit.name)
        .having(net_quantity > 0)
        .order_by(net_amount.desc(), Item.name)
        .limit(5)
    ).all()

    return {
        "summary": {
            "warningLotCount": len(expiry_lots),
            "expiredLotCount": expired_count,
            "expiringLotCount": len(expiry_lots) - expired_count,
            "periodInboundAmount": _money_text(period_inbound),
            "periodOutboundAmount": _money_text(period_outbound),
        },
        "expiryLots": expiry_lots,
        "trend": trend,
        "topConsumedItems": [{
            "itemId": row[0],
            "itemCode": row[1],
            "itemName": row[2],
            "unitName": row[3],
            "netQuantity": _number_text(_decimal(row[4])),
            "netAmount": _money_text(_decimal(row[5])),
        } for row in consumed_rows],
        "period": {
            "dateFrom": start_date.isoformat(),
            "dateTo": today.isoformat(),
            "trendDays": query.trend_days,
            "expiryDays": query.expiry_days,
        },
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
    }
