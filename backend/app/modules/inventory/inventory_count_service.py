from datetime import datetime, time
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError

from ...core.errors import ApiError
from ...extensions import db
from ..auth.service import format_datetime
from ..catalog.models import Unit
from ..farm.service import get_accessible_farm
from .models import (
    InventoryBalance,
    InventoryCount,
    InventoryCountLine,
    Item,
    StockDocument,
    StockMovementLine,
    Warehouse,
)
from .purchase_service import (
    COST_STEP,
    MONEY_STEP,
    _active_warehouse,
    _money_text,
    _number_text,
    _paginated,
    _require_write_access,
)


def _adjustment_document(count_id):
    return db.session.scalar(
        select(StockDocument).where(
            StockDocument.source_type == "INVENTORY_COUNT",
            StockDocument.source_id == count_id,
        )
    )


def _line_payload(line, item, unit):
    difference_amount = (line.difference_quantity * line.unit_cost).quantize(MONEY_STEP, rounding=ROUND_HALF_UP)
    return {
        "id": line.id,
        "itemId": item.id,
        "itemCode": item.code,
        "itemName": item.name,
        "unitName": unit.name,
        "lotNo": line.lot_no,
        "expiresOn": line.expires_on.isoformat() if line.expires_on else None,
        "bookQuantity": _number_text(line.book_quantity),
        "actualQuantity": _number_text(line.actual_quantity),
        "differenceQuantity": _number_text(line.difference_quantity),
        "unitCost": _number_text(line.unit_cost),
        "differenceAmount": _money_text(difference_amount),
        "reason": line.reason,
    }


def _count_lines(count_id, lock=False):
    statement = (
        select(InventoryCountLine, Item, Unit)
        .join(Item, Item.id == InventoryCountLine.item_id)
        .join(Unit, Unit.id == Item.unit_id)
        .where(InventoryCountLine.inventory_count_id == count_id)
        .order_by(Item.name, InventoryCountLine.lot_no, InventoryCountLine.id)
    )
    if lock:
        statement = statement.with_for_update()
    return db.session.execute(statement).all()


def _count_payload(count, warehouse, line_count, difference_line_count, lines=None):
    adjustment = _adjustment_document(count.id) if count.status == "POSTED" else None
    result = {
        "id": count.id,
        "farmId": count.farm_id,
        "countNo": count.count_no,
        "warehouseId": warehouse.id,
        "warehouseName": warehouse.name,
        "countDate": count.count_date.isoformat(),
        "status": count.status,
        "notes": count.notes,
        "version": count.version,
        "lineCount": line_count,
        "differenceLineCount": difference_line_count,
        "adjustmentDocumentNo": adjustment.document_no if adjustment else None,
        "postedAt": format_datetime(count.posted_at),
        "createdAt": format_datetime(count.created_at),
        "updatedAt": format_datetime(count.updated_at),
    }
    if lines is not None:
        result["lines"] = lines
    return result


def _count_row(count_id, lock=False):
    statement = (
        select(InventoryCount, Warehouse)
        .join(Warehouse, Warehouse.id == InventoryCount.warehouse_id)
        .where(InventoryCount.id == count_id)
    )
    if lock:
        statement = statement.with_for_update()
    return db.session.execute(statement).first()


def inventory_count_detail(count_id, actor):
    row = _count_row(count_id)
    if row is None:
        raise ApiError("盘点单不存在", 404, "INVENTORY_COUNT_NOT_FOUND")
    count, warehouse = row
    get_accessible_farm(count.farm_id, actor)
    line_rows = _count_lines(count.id)
    lines = [_line_payload(*line) for line in line_rows]
    difference_line_count = sum(1 for line, _, _ in line_rows if line.difference_quantity != 0)
    return _count_payload(count, warehouse, len(lines), difference_line_count, lines)


def list_inventory_counts(query, actor):
    get_accessible_farm(query.farm_id, actor)
    conditions = [InventoryCount.farm_id == query.farm_id]
    if query.keyword:
        conditions.append(or_(
            InventoryCount.count_no.contains(query.keyword, autoescape=True),
            Warehouse.name.contains(query.keyword, autoescape=True),
        ))
    if query.status != "all":
        conditions.append(InventoryCount.status == query.status)
    if query.date_from:
        conditions.append(InventoryCount.count_date >= query.date_from)
    if query.date_to:
        conditions.append(InventoryCount.count_date <= query.date_to)

    line_count = (
        select(func.count(InventoryCountLine.id))
        .where(InventoryCountLine.inventory_count_id == InventoryCount.id)
        .correlate(InventoryCount)
        .scalar_subquery()
    )
    difference_count = (
        select(func.coalesce(func.sum(case((InventoryCountLine.difference_quantity != 0, 1), else_=0)), 0))
        .where(InventoryCountLine.inventory_count_id == InventoryCount.id)
        .correlate(InventoryCount)
        .scalar_subquery()
    )
    total = db.session.scalar(
        select(func.count(InventoryCount.id)).join(Warehouse).where(*conditions)
    ) or 0
    rows = db.session.execute(
        select(InventoryCount, Warehouse, line_count, difference_count)
        .join(Warehouse, Warehouse.id == InventoryCount.warehouse_id)
        .where(*conditions)
        .order_by(InventoryCount.count_date.desc(), InventoryCount.id.desc())
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
    ).all()
    return _paginated(
        [_count_payload(count, warehouse, lines, differences) for count, warehouse, lines, differences in rows],
        query,
        total,
    )


def _warehouse_lots(farm_id, warehouse_id):
    quantity = func.sum(StockMovementLine.quantity_delta)
    return db.session.execute(
        select(
            StockMovementLine.item_id,
            StockMovementLine.lot_no,
            func.max(StockMovementLine.expires_on),
            quantity,
        )
        .join(StockDocument, StockDocument.id == StockMovementLine.stock_document_id)
        .where(
            StockDocument.farm_id == farm_id,
            StockDocument.status == "POSTED",
            StockMovementLine.warehouse_id == warehouse_id,
        )
        .group_by(StockMovementLine.item_id, StockMovementLine.lot_no)
        .having(quantity > 0)
        .order_by(StockMovementLine.item_id, StockMovementLine.lot_no)
    ).all()


def create_inventory_count(payload, actor):
    _require_write_access(payload.farm_id, actor)
    if payload.count_date > datetime.now().date():
        raise ApiError("盘点日期不能晚于今天", 400, "INVENTORY_COUNT_DATE_IN_FUTURE", "countDate")
    warehouse = _active_warehouse(payload.farm_id, payload.warehouse_id)
    if db.session.scalar(select(StockDocument.id).where(
        StockDocument.farm_id == payload.farm_id,
        StockDocument.document_no == payload.count_no,
    )):
        raise ApiError("盘点单号已被库存业务使用", 409, "STOCK_DOCUMENT_NO_EXISTS", "countNo")

    lots = _warehouse_lots(payload.farm_id, warehouse.id)
    if not lots:
        raise ApiError("该仓库暂无可盘点库存", 409, "INVENTORY_COUNT_NO_STOCK")
    item_ids = sorted({item_id for item_id, _, _, _ in lots})
    costs = {
        balance.item_id: Decimal(balance.average_cost or 0)
        for balance in db.session.scalars(
            select(InventoryBalance).where(
                InventoryBalance.warehouse_id == warehouse.id,
                InventoryBalance.item_id.in_(item_ids),
            )
        ).all()
    }

    count = InventoryCount(
        farm_id=payload.farm_id,
        count_no=payload.count_no,
        warehouse_id=warehouse.id,
        count_date=payload.count_date,
        notes=payload.notes,
        created_by_id=actor.id,
        updated_by_id=actor.id,
    )
    db.session.add(count)
    try:
        db.session.flush()
        for item_id, lot_no, expires_on, quantity in lots:
            book_quantity = Decimal(quantity)
            db.session.add(InventoryCountLine(
                inventory_count_id=count.id,
                item_id=item_id,
                lot_no=lot_no,
                expires_on=expires_on,
                book_quantity=book_quantity,
                actual_quantity=book_quantity,
                difference_quantity=Decimal("0"),
                unit_cost=costs.get(item_id, Decimal("0")),
            ))
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ApiError("该农场内盘点单号已存在", 409, "INVENTORY_COUNT_NO_EXISTS", "countNo") from error
    return inventory_count_detail(count.id, actor)


def update_inventory_count(count_id, payload, actor):
    row = _count_row(count_id, lock=True)
    if row is None:
        raise ApiError("盘点单不存在", 404, "INVENTORY_COUNT_NOT_FOUND")
    count, warehouse = row
    _require_write_access(count.farm_id, actor)
    if count.status != "DRAFT":
        raise ApiError("只有草稿盘点单可以修改", 409, "INVENTORY_COUNT_NOT_DRAFT")
    if count.version != payload.version:
        raise ApiError("盘点单已被其他人修改，请刷新后重试", 409, "INVENTORY_COUNT_VERSION_CONFLICT")

    line_rows = _count_lines(count.id, lock=True)
    lines = {line.id: line for line, _, _ in line_rows}
    updates = {line.id: line for line in payload.lines}
    if set(lines) != set(updates):
        raise ApiError("盘点明细与当前草稿不一致，请刷新后重试", 409, "INVENTORY_COUNT_LINES_CHANGED")
    for line_id, line in lines.items():
        update = updates[line_id]
        difference = update.actual_quantity - line.book_quantity
        if difference != 0 and not update.reason:
            raise ApiError("存在盘点差异时必须填写原因", 400, "INVENTORY_COUNT_REASON_REQUIRED", "reason")
        line.actual_quantity = update.actual_quantity
        line.difference_quantity = difference
        line.reason = update.reason
    count.notes = payload.notes
    count.version += 1
    count.updated_by_id = actor.id
    db.session.commit()
    return inventory_count_detail(count.id, actor)


def cancel_inventory_count(count_id, payload, actor):
    row = _count_row(count_id, lock=True)
    if row is None:
        raise ApiError("盘点单不存在", 404, "INVENTORY_COUNT_NOT_FOUND")
    count, warehouse = row
    _require_write_access(count.farm_id, actor)
    if count.status == "CANCELLED":
        db.session.rollback()
        return inventory_count_detail(count.id, actor)
    if count.status == "POSTED":
        raise ApiError("已过账盘点单不能取消", 409, "INVENTORY_COUNT_ALREADY_POSTED")
    if count.version != payload.version:
        raise ApiError("盘点单已被其他人修改，请刷新后重试", 409, "INVENTORY_COUNT_VERSION_CONFLICT")
    count.status = "CANCELLED"
    count.version += 1
    count.updated_by_id = actor.id
    db.session.commit()
    return inventory_count_detail(count.id, actor)


def post_inventory_count(count_id, payload, actor):
    row = _count_row(count_id, lock=True)
    if row is None:
        raise ApiError("盘点单不存在", 404, "INVENTORY_COUNT_NOT_FOUND")
    count, warehouse = row
    _require_write_access(count.farm_id, actor)
    if count.status == "POSTED":
        db.session.rollback()
        return inventory_count_detail(count.id, actor)
    if count.status == "CANCELLED":
        raise ApiError("已取消盘点单不能过账", 409, "INVENTORY_COUNT_CANCELLED")
    if count.version != payload.version:
        raise ApiError("盘点单已被其他人修改，请刷新后重试", 409, "INVENTORY_COUNT_VERSION_CONFLICT")
    _active_warehouse(count.farm_id, count.warehouse_id)

    line_rows = _count_lines(count.id, lock=True)
    stored_by_key = {(line.item_id, line.lot_no or ""): line for line, _, _ in line_rows}
    current_lots = _warehouse_lots(count.farm_id, count.warehouse_id)
    current_by_key = {
        (item_id, lot_no or ""): (Decimal(quantity), expires_on)
        for item_id, lot_no, expires_on, quantity in current_lots
    }
    item_ids = sorted({item_id for item_id, _ in set(stored_by_key) | set(current_by_key)})
    balances = db.session.scalars(
        select(InventoryBalance)
        .where(
            InventoryBalance.warehouse_id == count.warehouse_id,
            InventoryBalance.item_id.in_(item_ids),
        )
        .order_by(InventoryBalance.item_id)
        .with_for_update()
    ).all()
    current_lots = _warehouse_lots(count.farm_id, count.warehouse_id)
    current_by_key = {
        (item_id, lot_no or ""): (Decimal(quantity), expires_on)
        for item_id, lot_no, expires_on, quantity in current_lots
    }
    if set(stored_by_key) != set(current_by_key):
        raise ApiError("盘点期间库存批号已变化，请取消后重新生成盘点单", 409, "INVENTORY_COUNT_STALE")
    for key, line in stored_by_key.items():
        current_quantity, _ = current_by_key[key]
        if current_quantity != line.book_quantity:
            raise ApiError(
                "盘点期间库存数量已变化，请取消后重新生成盘点单",
                409,
                "INVENTORY_COUNT_STALE",
                details={"itemId": line.item_id, "currentQuantity": _number_text(current_quantity)},
            )

    balance_by_item = {balance.item_id: balance for balance in balances}
    document = StockDocument(
        farm_id=count.farm_id,
        document_no=count.count_no,
        document_type="INVENTORY_ADJUSTMENT",
        source_type="INVENTORY_COUNT",
        source_id=count.id,
        occurred_at=datetime.combine(count.count_date, time.min),
        created_by_id=actor.id,
    )
    db.session.add(document)
    try:
        db.session.flush()
        delta_by_item = {}
        for line, _, _ in line_rows:
            balance = balance_by_item.get(line.item_id)
            if balance is None:
                raise ApiError("库存余额不存在，请重新生成盘点单", 409, "INVENTORY_COUNT_STALE")
            unit_cost = Decimal(balance.average_cost or 0).quantize(COST_STEP, rounding=ROUND_HALF_UP)
            line.unit_cost = unit_cost
            delta_by_item[line.item_id] = delta_by_item.get(line.item_id, Decimal("0")) + line.difference_quantity
            if line.difference_quantity != 0:
                db.session.add(StockMovementLine(
                    stock_document_id=document.id,
                    warehouse_id=count.warehouse_id,
                    item_id=line.item_id,
                    quantity_delta=line.difference_quantity,
                    unit_cost=unit_cost,
                    lot_no=line.lot_no,
                    expires_on=line.expires_on,
                ))
        for item_id, delta in delta_by_item.items():
            balance = balance_by_item[item_id]
            new_quantity = Decimal(balance.quantity or 0) + delta
            if new_quantity < 0:
                raise ApiError("盘点结果不能形成负库存", 409, "INVENTORY_COUNT_NEGATIVE_STOCK")
            balance.quantity = new_quantity
        count.status = "POSTED"
        count.version += 1
        count.posted_at = datetime.now()
        count.posted_by_id = actor.id
        count.updated_by_id = actor.id
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ApiError("盘点过账冲突，请刷新后重试", 409, "INVENTORY_COUNT_POST_CONFLICT") from error
    return inventory_count_detail(count.id, actor)
