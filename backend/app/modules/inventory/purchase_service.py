from datetime import datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
from math import ceil

from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError

from ...core.errors import ApiError
from ...extensions import db
from ..auth.service import format_datetime
from ..catalog.models import Unit
from ..farm.models import Barn, Plot
from ..farm.service import get_accessible_farm
from .models import (
    InventoryBalance,
    Item,
    PurchaseOrder,
    PurchaseOrderLine,
    StockDocument,
    StockMovementLine,
    Supplier,
    Warehouse,
)


MONEY_STEP = Decimal("0.01")
COST_STEP = Decimal("0.0001")
PRODUCTION_DOCUMENT_TYPES = ("PRODUCTION_ISSUE", "PRODUCTION_RETURN")
PURCHASE_RETURN_SOURCE_TYPE = "PURCHASE_ORDER_RETURN"


def _number_text(value):
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _money_text(value):
    return format(value, ".2f")


def _paginated(items, query, total, **extra):
    return {
        "items": items,
        "pagination": {
            "page": query.page,
            "pageSize": query.page_size,
            "total": total,
            "totalPages": ceil(total / query.page_size) if total else 0,
        },
        **extra,
    }


def _require_write_access(farm_id, actor, roles=("manager", "operator")):
    farm, access_role = get_accessible_farm(farm_id, actor)
    if actor.role != "admin" and access_role not in roles:
        raise ApiError("当前农场角色没有业务写入权限", 403, "FARM_WRITE_DENIED")
    if not farm.is_active:
        raise ApiError("农场已停用，不能办理业务", 409, "FARM_DISABLED")
    return farm


def supplier_payload(supplier):
    return {
        "id": supplier.id,
        "farmId": supplier.farm_id,
        "code": supplier.code,
        "name": supplier.name,
        "contact": supplier.contact,
        "phone": supplier.phone,
        "address": supplier.address,
        "isActive": supplier.is_active,
        "createdAt": format_datetime(supplier.created_at),
        "updatedAt": format_datetime(supplier.updated_at),
    }


def list_suppliers(query, actor):
    get_accessible_farm(query.farm_id, actor)
    conditions = [Supplier.farm_id == query.farm_id]
    if query.keyword:
        conditions.append(or_(
            Supplier.code.contains(query.keyword, autoescape=True),
            Supplier.name.contains(query.keyword, autoescape=True),
            Supplier.contact.contains(query.keyword, autoescape=True),
            Supplier.phone.contains(query.keyword, autoescape=True),
        ))
    if query.status == "active":
        conditions.append(Supplier.is_active.is_(True))
    elif query.status == "disabled":
        conditions.append(Supplier.is_active.is_(False))
    total = db.session.scalar(select(func.count(Supplier.id)).where(*conditions)) or 0
    suppliers = db.session.scalars(
        select(Supplier)
        .where(*conditions)
        .order_by(Supplier.is_active.desc(), Supplier.name, Supplier.id)
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
    ).all()
    return _paginated([supplier_payload(item) for item in suppliers], query, total)


def create_supplier(payload, actor):
    _require_write_access(payload.farm_id, actor, ("manager",))
    supplier = Supplier(
        farm_id=payload.farm_id,
        code=payload.code,
        name=payload.name,
        contact=payload.contact,
        phone=payload.phone,
        address=payload.address,
        created_by_id=actor.id,
        updated_by_id=actor.id,
    )
    db.session.add(supplier)
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ApiError("该农场内供应商编号已存在", 409, "SUPPLIER_CODE_EXISTS", "code") from error
    return supplier_payload(supplier)


def update_supplier(supplier_id, payload, actor):
    supplier = db.session.get(Supplier, supplier_id)
    if supplier is None:
        raise ApiError("供应商不存在", 404, "SUPPLIER_NOT_FOUND")
    _require_write_access(supplier.farm_id, actor, ("manager",))
    for field in ("code", "name", "contact", "phone", "address", "is_active"):
        if field in payload.model_fields_set:
            setattr(supplier, field, getattr(payload, field))
    supplier.updated_by_id = actor.id
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ApiError("该农场内供应商编号已存在", 409, "SUPPLIER_CODE_EXISTS", "code") from error
    return supplier_payload(supplier)


def _active_supplier(farm_id, supplier_id):
    supplier = db.session.get(Supplier, supplier_id)
    if supplier is None:
        raise ApiError("供应商不存在", 404, "SUPPLIER_NOT_FOUND")
    if supplier.farm_id != farm_id:
        raise ApiError("不能引用其他农场的供应商", 409, "SUPPLIER_FARM_MISMATCH")
    if not supplier.is_active:
        raise ApiError("供应商已停用", 409, "SUPPLIER_DISABLED")
    return supplier


def _active_warehouse(farm_id, warehouse_id):
    warehouse = db.session.get(Warehouse, warehouse_id)
    if warehouse is None:
        raise ApiError("仓库不存在", 404, "WAREHOUSE_NOT_FOUND")
    if warehouse.farm_id != farm_id:
        raise ApiError("不能引用其他农场的仓库", 409, "WAREHOUSE_FARM_MISMATCH")
    if not warehouse.is_active:
        raise ApiError("仓库已停用", 409, "WAREHOUSE_DISABLED")
    return warehouse


def _validated_lines(farm_id, line_payloads):
    item_ids = sorted({line.item_id for line in line_payloads})
    items = {
        item.id: item
        for item in db.session.scalars(select(Item).where(Item.id.in_(item_ids))).all()
    }
    result = []
    total = Decimal("0")
    for line in line_payloads:
        item = items.get(line.item_id)
        if item is None:
            raise ApiError("采购物料不存在", 404, "ITEM_NOT_FOUND")
        if item.farm_id != farm_id:
            raise ApiError("不能采购其他农场的物料", 409, "ITEM_FARM_MISMATCH")
        if not item.is_active:
            raise ApiError(f"物料“{item.name}”已停用", 409, "ITEM_DISABLED")
        if item.lot_tracking and not line.lot_no:
            raise ApiError(f"物料“{item.name}”必须填写批号", 400, "LOT_NO_REQUIRED")
        if line.expires_on and not line.lot_no:
            raise ApiError("填写有效期时必须同时填写批号", 400, "LOT_NO_REQUIRED")
        amount = (line.quantity * line.unit_price).quantize(MONEY_STEP, rounding=ROUND_HALF_UP)
        total += amount
        result.append((line, item, amount))
    return result, total.quantize(MONEY_STEP, rounding=ROUND_HALF_UP)


def _purchase_returned_quantities(line_ids):
    if not line_ids:
        return {}
    rows = db.session.execute(
        select(
            StockDocument.source_id,
            func.coalesce(func.sum(StockMovementLine.quantity_delta * -1), 0),
        )
        .join(StockMovementLine, StockMovementLine.stock_document_id == StockDocument.id)
        .where(
            StockDocument.document_type == "PURCHASE_RETURN",
            StockDocument.status == "POSTED",
            StockDocument.source_type == PURCHASE_RETURN_SOURCE_TYPE,
            StockDocument.source_id.in_(line_ids),
        )
        .group_by(StockDocument.source_id)
    ).all()
    return {line_id: Decimal(quantity or 0) for line_id, quantity in rows}


def _purchase_line_payload(line, item, unit, returned_quantity=Decimal("0")):
    returnable_quantity = max(Decimal(line.quantity) - returned_quantity, Decimal("0"))
    return {
        "id": line.id,
        "itemId": item.id,
        "itemCode": item.code,
        "itemName": item.name,
        "unitName": unit.name,
        "quantity": _number_text(line.quantity),
        "unitPrice": _number_text(line.unit_price),
        "amount": _money_text(line.amount),
        "lotNo": line.lot_no,
        "expiresOn": line.expires_on.isoformat() if line.expires_on else None,
        "returnedQuantity": _number_text(returned_quantity),
        "returnableQuantity": _number_text(returnable_quantity),
    }


def _purchase_lines(purchase_order_id):
    rows = db.session.execute(
        select(PurchaseOrderLine, Item, Unit)
        .join(Item, Item.id == PurchaseOrderLine.item_id)
        .join(Unit, Unit.id == Item.unit_id)
        .where(PurchaseOrderLine.purchase_order_id == purchase_order_id)
        .order_by(PurchaseOrderLine.id)
    ).all()
    returned_quantities = _purchase_returned_quantities([row[0].id for row in rows])
    return [
        _purchase_line_payload(*row, returned_quantities.get(row[0].id, Decimal("0")))
        for row in rows
    ]


def _purchase_payload(order, supplier, warehouse, line_count, lines=None):
    result = {
        "id": order.id,
        "farmId": order.farm_id,
        "orderNo": order.order_no,
        "supplierId": supplier.id,
        "supplierName": supplier.name,
        "warehouseId": warehouse.id,
        "warehouseName": warehouse.name,
        "orderDate": order.order_date.isoformat(),
        "status": order.status,
        "totalAmount": _money_text(order.total_amount),
        "notes": order.notes,
        "lineCount": line_count,
        "version": order.version,
        "postedAt": format_datetime(order.posted_at),
        "createdAt": format_datetime(order.created_at),
        "updatedAt": format_datetime(order.updated_at),
    }
    if lines is not None:
        result["lines"] = lines
    return result


def _purchase_row(purchase_id, lock=False):
    statement = select(PurchaseOrder).where(PurchaseOrder.id == purchase_id)
    if lock:
        statement = statement.with_for_update()
    order = db.session.scalar(statement)
    if order is None:
        raise ApiError("采购单不存在", 404, "PURCHASE_NOT_FOUND")
    return order


def purchase_detail(purchase_id, actor):
    order = _purchase_row(purchase_id)
    get_accessible_farm(order.farm_id, actor)
    supplier = db.session.get(Supplier, order.supplier_id)
    warehouse = db.session.get(Warehouse, order.warehouse_id)
    lines = _purchase_lines(order.id)
    return _purchase_payload(order, supplier, warehouse, len(lines), lines)


def list_purchases(query, actor):
    get_accessible_farm(query.farm_id, actor)
    conditions = [PurchaseOrder.farm_id == query.farm_id]
    if query.keyword:
        conditions.append(or_(
            PurchaseOrder.order_no.contains(query.keyword, autoescape=True),
            Supplier.name.contains(query.keyword, autoescape=True),
        ))
    if query.status != "all":
        conditions.append(PurchaseOrder.status == query.status)
    if query.date_from:
        conditions.append(PurchaseOrder.order_date >= query.date_from)
    if query.date_to:
        conditions.append(PurchaseOrder.order_date <= query.date_to)

    line_counts = (
        select(PurchaseOrderLine.purchase_order_id, func.count(PurchaseOrderLine.id).label("line_count"))
        .group_by(PurchaseOrderLine.purchase_order_id)
        .subquery()
    )
    base = (
        select(PurchaseOrder)
        .join(Supplier, Supplier.id == PurchaseOrder.supplier_id)
        .where(*conditions)
    )
    total = db.session.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.session.execute(
        select(PurchaseOrder, Supplier, Warehouse, func.coalesce(line_counts.c.line_count, 0))
        .join(Supplier, Supplier.id == PurchaseOrder.supplier_id)
        .join(Warehouse, Warehouse.id == PurchaseOrder.warehouse_id)
        .outerjoin(line_counts, line_counts.c.purchase_order_id == PurchaseOrder.id)
        .where(*conditions)
        .order_by(PurchaseOrder.order_date.desc(), PurchaseOrder.id.desc())
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
    ).all()
    return _paginated([_purchase_payload(*row) for row in rows], query, total)


def _add_purchase_lines(order, validated_lines):
    for line, _, amount in validated_lines:
        db.session.add(PurchaseOrderLine(
            purchase_order_id=order.id,
            item_id=line.item_id,
            quantity=line.quantity,
            unit_price=line.unit_price,
            amount=amount,
            lot_no=line.lot_no,
            expires_on=line.expires_on,
        ))


def create_purchase(payload, actor):
    _require_write_access(payload.farm_id, actor)
    _active_supplier(payload.farm_id, payload.supplier_id)
    _active_warehouse(payload.farm_id, payload.warehouse_id)
    validated_lines, total = _validated_lines(payload.farm_id, payload.lines)
    order = PurchaseOrder(
        farm_id=payload.farm_id,
        order_no=payload.order_no,
        supplier_id=payload.supplier_id,
        warehouse_id=payload.warehouse_id,
        order_date=payload.order_date,
        total_amount=total,
        notes=payload.notes,
        created_by_id=actor.id,
        updated_by_id=actor.id,
    )
    db.session.add(order)
    try:
        db.session.flush()
        _add_purchase_lines(order, validated_lines)
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ApiError("该农场内采购单号已存在", 409, "PURCHASE_NO_EXISTS", "orderNo") from error
    return purchase_detail(order.id, actor)


def update_purchase(purchase_id, payload, actor):
    order = _purchase_row(purchase_id, lock=True)
    _require_write_access(order.farm_id, actor)
    if payload.farm_id != order.farm_id:
        raise ApiError("不能将采购单转移到其他农场", 409, "PURCHASE_FARM_MISMATCH")
    if order.status != "DRAFT":
        raise ApiError("只有草稿采购单可以修改", 409, "PURCHASE_NOT_EDITABLE")
    if payload.version != order.version:
        raise ApiError("采购单已被其他操作更新，请刷新后重试", 409, "PURCHASE_VERSION_CONFLICT")
    _active_supplier(order.farm_id, payload.supplier_id)
    _active_warehouse(order.farm_id, payload.warehouse_id)
    validated_lines, total = _validated_lines(order.farm_id, payload.lines)
    order.order_no = payload.order_no
    order.supplier_id = payload.supplier_id
    order.warehouse_id = payload.warehouse_id
    order.order_date = payload.order_date
    order.total_amount = total
    order.notes = payload.notes
    order.version += 1
    order.updated_by_id = actor.id
    try:
        db.session.execute(delete(PurchaseOrderLine).where(PurchaseOrderLine.purchase_order_id == order.id))
        _add_purchase_lines(order, validated_lines)
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ApiError("该农场内采购单号已存在", 409, "PURCHASE_NO_EXISTS", "orderNo") from error
    return purchase_detail(order.id, actor)


def cancel_purchase(purchase_id, payload, actor):
    order = _purchase_row(purchase_id, lock=True)
    _require_write_access(order.farm_id, actor)
    if order.status == "CANCELLED":
        db.session.rollback()
        return purchase_detail(order.id, actor)
    if order.status != "DRAFT":
        raise ApiError("只有草稿采购单可以取消", 409, "PURCHASE_NOT_CANCELLABLE")
    if payload.version != order.version:
        raise ApiError("采购单已被其他操作更新，请刷新后重试", 409, "PURCHASE_VERSION_CONFLICT")
    order.status = "CANCELLED"
    order.version += 1
    order.updated_by_id = actor.id
    db.session.commit()
    return purchase_detail(order.id, actor)


def post_purchase(purchase_id, payload, actor):
    order = _purchase_row(purchase_id, lock=True)
    _require_write_access(order.farm_id, actor)
    if order.status == "POSTED":
        db.session.rollback()
        return purchase_detail(order.id, actor)
    if order.status != "DRAFT":
        raise ApiError("采购单当前状态不能过账", 409, "PURCHASE_NOT_POSTABLE")
    if payload.version != order.version:
        raise ApiError("采购单已被其他操作更新，请刷新后重试", 409, "PURCHASE_VERSION_CONFLICT")
    _active_supplier(order.farm_id, order.supplier_id)
    warehouse = _active_warehouse(order.farm_id, order.warehouse_id)

    rows = db.session.execute(
        select(PurchaseOrderLine, Item)
        .join(Item, Item.id == PurchaseOrderLine.item_id)
        .where(PurchaseOrderLine.purchase_order_id == order.id)
        .order_by(Item.id)
        .with_for_update()
    ).all()
    if not rows:
        raise ApiError("采购单没有明细，不能过账", 409, "PURCHASE_LINES_REQUIRED")
    for line, item in rows:
        if item.farm_id != order.farm_id or not item.is_active:
            raise ApiError(f"物料“{item.name}”不可用于当前采购", 409, "ITEM_NOT_AVAILABLE")
        if item.lot_tracking and not line.lot_no:
            raise ApiError(f"物料“{item.name}”必须填写批号", 400, "LOT_NO_REQUIRED")

    document = StockDocument(
        farm_id=order.farm_id,
        document_no=f"IN-{order.order_no}",
        document_type="PURCHASE_RECEIPT",
        to_warehouse_id=warehouse.id,
        source_type="PURCHASE_ORDER",
        source_id=order.id,
        occurred_at=datetime.now(),
        created_by_id=actor.id,
    )
    db.session.add(document)
    db.session.flush()
    for line, item in rows:
        balance = db.session.scalar(
            select(InventoryBalance)
            .where(
                InventoryBalance.warehouse_id == warehouse.id,
                InventoryBalance.item_id == item.id,
            )
            .with_for_update()
        )
        if balance is None:
            balance = InventoryBalance(
                farm_id=order.farm_id,
                warehouse_id=warehouse.id,
                item_id=item.id,
            )
            db.session.add(balance)
        old_quantity = balance.quantity or Decimal("0")
        old_cost = balance.average_cost or Decimal("0")
        new_quantity = old_quantity + line.quantity
        balance.average_cost = (
            ((old_quantity * old_cost) + (line.quantity * line.unit_price)) / new_quantity
        ).quantize(COST_STEP, rounding=ROUND_HALF_UP)
        balance.quantity = new_quantity
        db.session.add(StockMovementLine(
            stock_document_id=document.id,
            warehouse_id=warehouse.id,
            item_id=item.id,
            quantity_delta=line.quantity,
            unit_cost=line.unit_price,
            lot_no=line.lot_no,
            expires_on=line.expires_on,
        ))

    order.status = "POSTED"
    order.posted_at = datetime.now()
    order.posted_by_id = actor.id
    order.updated_by_id = actor.id
    order.version += 1
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ApiError("采购单过账冲突，请刷新后重试", 409, "PURCHASE_POST_CONFLICT") from error
    return purchase_detail(order.id, actor)


def _purchase_return_payload(document):
    row = db.session.execute(
        select(StockMovementLine, Item, Unit, Warehouse)
        .join(Item, Item.id == StockMovementLine.item_id)
        .join(Unit, Unit.id == Item.unit_id)
        .join(Warehouse, Warehouse.id == StockMovementLine.warehouse_id)
        .where(StockMovementLine.stock_document_id == document.id)
    ).first()
    purchase_line = db.session.get(PurchaseOrderLine, document.source_id)
    purchase = db.session.get(PurchaseOrder, purchase_line.purchase_order_id) if purchase_line else None
    supplier = db.session.get(Supplier, purchase.supplier_id) if purchase else None
    if row is None or purchase_line is None or purchase is None or supplier is None:
        raise ApiError("采购退货流水不完整，请联系管理员", 500, "PURCHASE_RETURN_LEDGER_INVALID")
    movement, item, unit, warehouse = row
    quantity = abs(movement.quantity_delta)
    inventory_amount = (quantity * movement.unit_cost).quantize(MONEY_STEP, rounding=ROUND_HALF_UP)
    refund_amount = (quantity * purchase_line.unit_price).quantize(MONEY_STEP, rounding=ROUND_HALF_UP)
    return {
        "id": document.id,
        "farmId": document.farm_id,
        "documentNo": document.document_no,
        "documentType": document.document_type,
        "purchaseId": purchase.id,
        "purchaseOrderNo": purchase.order_no,
        "purchaseLineId": purchase_line.id,
        "supplierId": supplier.id,
        "supplierName": supplier.name,
        "returnDate": document.occurred_at.date().isoformat(),
        "warehouseId": warehouse.id,
        "warehouseName": warehouse.name,
        "itemId": item.id,
        "itemCode": item.code,
        "itemName": item.name,
        "unitName": unit.name,
        "quantity": _number_text(quantity),
        "inventoryUnitCost": _number_text(movement.unit_cost),
        "inventoryAmount": _money_text(inventory_amount),
        "refundUnitPrice": _number_text(purchase_line.unit_price),
        "refundAmount": _money_text(refund_amount),
        "lotNo": movement.lot_no,
        "expiresOn": movement.expires_on.isoformat() if movement.expires_on else None,
        "createdAt": format_datetime(document.created_at),
    }


def _matching_purchase_return(purchase_return, payload):
    return (
        purchase_return["purchaseId"] == payload.purchase_id
        and purchase_return["purchaseLineId"] == payload.purchase_line_id
        and purchase_return["returnDate"] == payload.return_date.isoformat()
        and purchase_return["warehouseId"] == payload.warehouse_id
        and Decimal(purchase_return["quantity"]) == payload.quantity
    )


def _existing_purchase_return(payload):
    document = db.session.scalar(
        select(StockDocument).where(
            StockDocument.farm_id == payload.farm_id,
            StockDocument.document_no == payload.document_no,
        )
    )
    if document is None:
        return None
    if document.document_type != "PURCHASE_RETURN":
        raise ApiError("该库存单号已被其他业务使用", 409, "STOCK_DOCUMENT_NO_EXISTS", "documentNo")
    purchase_return = _purchase_return_payload(document)
    if not _matching_purchase_return(purchase_return, payload):
        raise ApiError("采购退货单号已存在且内容不同", 409, "PURCHASE_RETURN_NO_EXISTS", "documentNo")
    return purchase_return


def create_purchase_return(payload, actor):
    _require_write_access(payload.farm_id, actor)
    existing = _existing_purchase_return(payload)
    if existing is not None:
        db.session.rollback()
        return existing, False
    if payload.return_date > datetime.now().date():
        raise ApiError("采购退货日期不能晚于今天", 400, "PURCHASE_RETURN_DATE_IN_FUTURE", "returnDate")

    purchase = _purchase_row(payload.purchase_id, lock=True)
    if purchase.farm_id != payload.farm_id:
        raise ApiError("不能退回其他农场的采购物料", 409, "PURCHASE_RETURN_FARM_MISMATCH")
    if purchase.status != "POSTED":
        raise ApiError("只有已过账采购单可以退货", 409, "PURCHASE_NOT_RETURNABLE")
    if payload.return_date < purchase.order_date:
        raise ApiError("采购退货日期不能早于采购日期", 400, "PURCHASE_RETURN_DATE_BEFORE_PURCHASE", "returnDate")

    purchase_line = db.session.get(PurchaseOrderLine, payload.purchase_line_id)
    if purchase_line is None or purchase_line.purchase_order_id != purchase.id:
        raise ApiError("采购明细不存在或不属于该采购单", 404, "PURCHASE_LINE_NOT_FOUND", "purchaseLineId")
    warehouse = _active_warehouse(payload.farm_id, payload.warehouse_id)
    item = _active_stock_item(payload.farm_id, purchase_line.item_id, "办理采购退货")

    balance = db.session.scalar(
        select(InventoryBalance)
        .where(
            InventoryBalance.warehouse_id == warehouse.id,
            InventoryBalance.item_id == item.id,
        )
        .with_for_update()
    )
    current_quantity = Decimal(balance.quantity or 0) if balance else Decimal("0")
    returned_quantity = _purchase_returned_quantities([purchase_line.id]).get(
        purchase_line.id,
        Decimal("0"),
    )
    returnable_quantity = max(Decimal(purchase_line.quantity) - returned_quantity, Decimal("0"))
    if returnable_quantity < payload.quantity:
        raise ApiError(
            f"该采购明细可退“{item.name}”不足，可退 {_number_text(returnable_quantity)}",
            409,
            "PURCHASE_RETURN_EXCEEDS_RECEIPT",
            "quantity",
            {"available": _number_text(returnable_quantity)},
        )
    if current_quantity < payload.quantity:
        raise ApiError(
            f"{warehouse.name} 的“{item.name}”库存不足，可用 {_number_text(current_quantity)}",
            409,
            "STOCK_INSUFFICIENT",
            "quantity",
            {"available": _number_text(current_quantity)},
        )
    if purchase_line.lot_no:
        lot_quantity, _ = _lot_stock(warehouse.id, item.id, purchase_line.lot_no)
        if lot_quantity < payload.quantity:
            raise ApiError(
                f"批号 {purchase_line.lot_no} 库存不足，可用 {_number_text(lot_quantity)}",
                409,
                "LOT_STOCK_INSUFFICIENT",
                "quantity",
                {"available": _number_text(lot_quantity)},
            )

    inventory_unit_cost = Decimal(balance.average_cost or 0)
    balance.quantity = current_quantity - payload.quantity
    if balance.quantity == 0:
        balance.average_cost = Decimal("0")
    document = StockDocument(
        farm_id=payload.farm_id,
        document_no=payload.document_no,
        document_type="PURCHASE_RETURN",
        from_warehouse_id=warehouse.id,
        source_type=PURCHASE_RETURN_SOURCE_TYPE,
        source_id=purchase_line.id,
        occurred_at=datetime.combine(payload.return_date, time.min),
        created_by_id=actor.id,
    )
    db.session.add(document)
    try:
        db.session.flush()
        db.session.add(StockMovementLine(
            stock_document_id=document.id,
            warehouse_id=warehouse.id,
            item_id=item.id,
            quantity_delta=-payload.quantity,
            unit_cost=inventory_unit_cost,
            lot_no=purchase_line.lot_no,
            expires_on=purchase_line.expires_on,
        ))
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        existing = _existing_purchase_return(payload)
        if existing is not None:
            return existing, False
        raise ApiError("采购退货过账冲突，请刷新后重试", 409, "PURCHASE_RETURN_POST_CONFLICT") from error
    return _purchase_return_payload(document), True


def _stock_transfer_payload(document):
    rows = db.session.execute(
        select(StockMovementLine, Item, Unit, Warehouse)
        .join(Item, Item.id == StockMovementLine.item_id)
        .join(Unit, Unit.id == Item.unit_id)
        .join(Warehouse, Warehouse.id == StockMovementLine.warehouse_id)
        .where(StockMovementLine.stock_document_id == document.id)
        .order_by(StockMovementLine.id)
    ).all()
    source_row = next(
        (row for row in rows if row[0].warehouse_id == document.from_warehouse_id and row[0].quantity_delta < 0),
        None,
    )
    destination_row = next(
        (row for row in rows if row[0].warehouse_id == document.to_warehouse_id and row[0].quantity_delta > 0),
        None,
    )
    if source_row is None or destination_row is None:
        raise ApiError("调拨流水不完整，请联系管理员", 500, "TRANSFER_LEDGER_INVALID")
    movement, item, unit, source_warehouse = source_row
    destination_warehouse = destination_row[3]
    quantity = abs(movement.quantity_delta)
    amount = (quantity * movement.unit_cost).quantize(MONEY_STEP, rounding=ROUND_HALF_UP)
    return {
        "id": document.id,
        "farmId": document.farm_id,
        "documentNo": document.document_no,
        "documentType": document.document_type,
        "fromWarehouseId": source_warehouse.id,
        "fromWarehouseName": source_warehouse.name,
        "toWarehouseId": destination_warehouse.id,
        "toWarehouseName": destination_warehouse.name,
        "transferDate": document.occurred_at.date().isoformat(),
        "itemId": item.id,
        "itemCode": item.code,
        "itemName": item.name,
        "unitName": unit.name,
        "quantity": _number_text(quantity),
        "unitCost": _number_text(movement.unit_cost),
        "amount": _money_text(amount),
        "lotNo": movement.lot_no,
        "expiresOn": movement.expires_on.isoformat() if movement.expires_on else None,
        "createdAt": format_datetime(document.created_at),
    }


def _matching_transfer(transfer, payload):
    return (
        transfer["fromWarehouseId"] == payload.from_warehouse_id
        and transfer["toWarehouseId"] == payload.to_warehouse_id
        and transfer["transferDate"] == payload.transfer_date.isoformat()
        and transfer["itemId"] == payload.item_id
        and Decimal(transfer["quantity"]) == payload.quantity
        and transfer["lotNo"] == payload.lot_no
    )


def _existing_stock_transfer(payload):
    document = db.session.scalar(
        select(StockDocument).where(
            StockDocument.farm_id == payload.farm_id,
            StockDocument.document_no == payload.document_no,
        )
    )
    if document is None:
        return None
    if document.document_type != "WAREHOUSE_TRANSFER":
        raise ApiError("该库存单号已被其他业务使用", 409, "STOCK_DOCUMENT_NO_EXISTS", "documentNo")
    transfer = _stock_transfer_payload(document)
    if not _matching_transfer(transfer, payload):
        raise ApiError("调拨单号已存在且内容不同", 409, "TRANSFER_NO_EXISTS", "documentNo")
    return transfer


def _active_stock_item(farm_id, item_id, action):
    item = db.session.get(Item, item_id)
    if item is None:
        raise ApiError("物料不存在", 404, "ITEM_NOT_FOUND")
    if item.farm_id != farm_id:
        raise ApiError("物料不属于当前农场", 409, "ITEM_FARM_MISMATCH")
    if not item.is_active:
        raise ApiError(f"物料已停用，不能{action}", 409, "ITEM_DISABLED")
    return item


def _lot_stock(warehouse_id, item_id, lot_no):
    quantity, expires_on = db.session.execute(
        select(
            func.coalesce(func.sum(StockMovementLine.quantity_delta), 0),
            func.max(StockMovementLine.expires_on),
        )
        .join(StockDocument, StockDocument.id == StockMovementLine.stock_document_id)
        .where(
            StockDocument.status == "POSTED",
            StockMovementLine.warehouse_id == warehouse_id,
            StockMovementLine.item_id == item_id,
            StockMovementLine.lot_no == lot_no,
        )
    ).one()
    return Decimal(quantity or 0), expires_on


def create_stock_transfer(payload, actor):
    _require_write_access(payload.farm_id, actor)
    existing = _existing_stock_transfer(payload)
    if existing is not None:
        db.session.rollback()
        return existing, False
    if payload.transfer_date > datetime.now().date():
        raise ApiError("调拨日期不能晚于今天", 400, "TRANSFER_DATE_IN_FUTURE", "transferDate")

    source_warehouse = _active_warehouse(payload.farm_id, payload.from_warehouse_id)
    destination_warehouse = _active_warehouse(payload.farm_id, payload.to_warehouse_id)
    if source_warehouse.id == destination_warehouse.id:
        raise ApiError("调出仓库和调入仓库不能相同", 400, "TRANSFER_WAREHOUSES_EQUAL")

    item = _active_stock_item(payload.farm_id, payload.item_id, "调拨")
    if item.lot_tracking and not payload.lot_no:
        raise ApiError(f"物料“{item.name}”必须填写批号", 400, "LOT_NO_REQUIRED", "lotNo")

    warehouse_ids = sorted((source_warehouse.id, destination_warehouse.id))
    balances = db.session.scalars(
        select(InventoryBalance)
        .where(
            InventoryBalance.item_id == item.id,
            InventoryBalance.warehouse_id.in_(warehouse_ids),
        )
        .order_by(InventoryBalance.warehouse_id)
        .with_for_update()
    ).all()
    balance_by_warehouse = {balance.warehouse_id: balance for balance in balances}
    source_balance = balance_by_warehouse.get(source_warehouse.id)
    source_quantity = Decimal(source_balance.quantity or 0) if source_balance else Decimal("0")
    if source_quantity < payload.quantity:
        raise ApiError(
            f"{source_warehouse.name} 的“{item.name}”库存不足，可用 {_number_text(source_quantity)}",
            409,
            "STOCK_INSUFFICIENT",
            "quantity",
            {"available": _number_text(source_quantity)},
        )

    expires_on = None
    if payload.lot_no:
        lot_quantity, expires_on = _lot_stock(source_warehouse.id, item.id, payload.lot_no)
        if lot_quantity < payload.quantity:
            raise ApiError(
                f"批号 {payload.lot_no} 库存不足，可用 {_number_text(lot_quantity)}",
                409,
                "LOT_STOCK_INSUFFICIENT",
                "quantity",
                {"available": _number_text(lot_quantity)},
            )

    source_cost = Decimal(source_balance.average_cost or 0)
    destination_balance = balance_by_warehouse.get(destination_warehouse.id)
    if destination_balance is None:
        destination_balance = InventoryBalance(
            farm_id=payload.farm_id,
            warehouse_id=destination_warehouse.id,
            item_id=item.id,
        )
        db.session.add(destination_balance)
    destination_quantity = Decimal(destination_balance.quantity or 0)
    destination_cost = Decimal(destination_balance.average_cost or 0)
    new_destination_quantity = destination_quantity + payload.quantity
    destination_balance.quantity = new_destination_quantity
    destination_balance.average_cost = (
        ((destination_quantity * destination_cost) + (payload.quantity * source_cost))
        / new_destination_quantity
    ).quantize(COST_STEP, rounding=ROUND_HALF_UP)
    source_balance.quantity = source_quantity - payload.quantity

    document = StockDocument(
        farm_id=payload.farm_id,
        document_no=payload.document_no,
        document_type="WAREHOUSE_TRANSFER",
        from_warehouse_id=source_warehouse.id,
        to_warehouse_id=destination_warehouse.id,
        source_type="MANUAL_TRANSFER",
        source_id=None,
        occurred_at=datetime.combine(payload.transfer_date, time.min),
        created_by_id=actor.id,
    )
    db.session.add(document)
    try:
        db.session.flush()
        for warehouse_id, quantity_delta in (
            (source_warehouse.id, -payload.quantity),
            (destination_warehouse.id, payload.quantity),
        ):
            db.session.add(StockMovementLine(
                stock_document_id=document.id,
                warehouse_id=warehouse_id,
                item_id=item.id,
                quantity_delta=quantity_delta,
                unit_cost=source_cost,
                lot_no=payload.lot_no,
                expires_on=expires_on,
            ))
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        existing = _existing_stock_transfer(payload)
        if existing is not None:
            return existing, False
        raise ApiError("库存调拨过账冲突，请刷新后重试", 409, "TRANSFER_POST_CONFLICT") from error
    return _stock_transfer_payload(document), True


def _production_cost_object(farm, cost_object_type, cost_object_id):
    if cost_object_type == "farm":
        return "FARM", farm.id

    model, label = (Barn, "圈舍") if cost_object_type == "barn" else (Plot, "地块")
    cost_object = db.session.get(model, cost_object_id)
    if cost_object is None:
        raise ApiError(f"{label}不存在", 404, "COST_OBJECT_NOT_FOUND", "costObjectId")
    if cost_object.farm_id != farm.id:
        raise ApiError(f"{label}不属于当前农场", 409, "COST_OBJECT_FARM_MISMATCH", "costObjectId")
    if not cost_object.is_active:
        raise ApiError(f"{label}已停用，不能办理领退料", 409, "COST_OBJECT_DISABLED", "costObjectId")
    return cost_object_type.upper(), cost_object.id


def _production_operation_payload(document):
    row = db.session.execute(
        select(StockMovementLine, Item, Unit, Warehouse)
        .join(Item, Item.id == StockMovementLine.item_id)
        .join(Unit, Unit.id == Item.unit_id)
        .join(Warehouse, Warehouse.id == StockMovementLine.warehouse_id)
        .where(StockMovementLine.stock_document_id == document.id)
    ).first()
    if row is None:
        raise ApiError("生产领退料流水不完整，请联系管理员", 500, "PRODUCTION_LEDGER_INVALID")
    movement, item, unit, warehouse = row
    quantity = abs(movement.quantity_delta)
    amount = (quantity * movement.unit_cost).quantize(MONEY_STEP, rounding=ROUND_HALF_UP)
    return {
        "id": document.id,
        "farmId": document.farm_id,
        "documentNo": document.document_no,
        "documentType": document.document_type,
        "operationType": "issue" if document.document_type == "PRODUCTION_ISSUE" else "return",
        "operationDate": document.occurred_at.date().isoformat(),
        "warehouseId": warehouse.id,
        "warehouseName": warehouse.name,
        "itemId": item.id,
        "itemCode": item.code,
        "itemName": item.name,
        "unitName": unit.name,
        "quantity": _number_text(quantity),
        "unitCost": _number_text(movement.unit_cost),
        "amount": _money_text(amount),
        "lotNo": movement.lot_no,
        "expiresOn": movement.expires_on.isoformat() if movement.expires_on else None,
        "costObjectType": movement.cost_object_type.lower(),
        "costObjectId": movement.cost_object_id,
        "createdAt": format_datetime(document.created_at),
    }


def _matching_production_operation(operation, payload):
    expected_document_type = "PRODUCTION_ISSUE" if payload.operation_type == "issue" else "PRODUCTION_RETURN"
    expected_cost_object_id = payload.farm_id if payload.cost_object_type == "farm" else payload.cost_object_id
    return (
        operation["documentType"] == expected_document_type
        and operation["operationDate"] == payload.operation_date.isoformat()
        and operation["warehouseId"] == payload.warehouse_id
        and operation["itemId"] == payload.item_id
        and Decimal(operation["quantity"]) == payload.quantity
        and operation["lotNo"] == payload.lot_no
        and operation["costObjectType"] == payload.cost_object_type
        and operation["costObjectId"] == expected_cost_object_id
    )


def _existing_production_operation(payload):
    document = db.session.scalar(
        select(StockDocument).where(
            StockDocument.farm_id == payload.farm_id,
            StockDocument.document_no == payload.document_no,
        )
    )
    if document is None:
        return None
    if document.document_type not in PRODUCTION_DOCUMENT_TYPES:
        raise ApiError("该库存单号已被其他业务使用", 409, "STOCK_DOCUMENT_NO_EXISTS", "documentNo")
    operation = _production_operation_payload(document)
    if not _matching_production_operation(operation, payload):
        raise ApiError("生产领退料单号已存在且内容不同", 409, "PRODUCTION_NO_EXISTS", "documentNo")
    return operation


def _outstanding_production_issue(
    farm_id,
    warehouse_id,
    item_id,
    lot_no,
    cost_object_type,
    cost_object_id,
    operation_date,
):
    quantity, amount, expires_on = db.session.execute(
        select(
            func.coalesce(func.sum(StockMovementLine.quantity_delta * -1), 0),
            func.coalesce(func.sum(StockMovementLine.quantity_delta * StockMovementLine.unit_cost * -1), 0),
            func.max(StockMovementLine.expires_on),
        )
        .join(StockDocument, StockDocument.id == StockMovementLine.stock_document_id)
        .where(
            StockDocument.farm_id == farm_id,
            StockDocument.status == "POSTED",
            StockDocument.document_type.in_(PRODUCTION_DOCUMENT_TYPES),
            StockDocument.occurred_at < datetime.combine(operation_date + timedelta(days=1), time.min),
            StockMovementLine.warehouse_id == warehouse_id,
            StockMovementLine.item_id == item_id,
            StockMovementLine.lot_no == lot_no,
            StockMovementLine.cost_object_type == cost_object_type,
            StockMovementLine.cost_object_id == cost_object_id,
        )
    ).one()
    return Decimal(quantity or 0), Decimal(amount or 0), expires_on


def create_production_stock_operation(payload, actor):
    farm = _require_write_access(payload.farm_id, actor)
    existing = _existing_production_operation(payload)
    if existing is not None:
        db.session.rollback()
        return existing, False
    if payload.operation_date > datetime.now().date():
        raise ApiError("领退料日期不能晚于今天", 400, "PRODUCTION_DATE_IN_FUTURE", "operationDate")

    warehouse = _active_warehouse(payload.farm_id, payload.warehouse_id)
    item = _active_stock_item(payload.farm_id, payload.item_id, "办理领退料")
    if item.lot_tracking and not payload.lot_no:
        raise ApiError(f"物料“{item.name}”必须填写批号", 400, "LOT_NO_REQUIRED", "lotNo")
    cost_object_type, cost_object_id = _production_cost_object(
        farm,
        payload.cost_object_type,
        payload.cost_object_id,
    )

    balance = db.session.scalar(
        select(InventoryBalance)
        .where(
            InventoryBalance.warehouse_id == warehouse.id,
            InventoryBalance.item_id == item.id,
        )
        .with_for_update()
    )
    current_quantity = Decimal(balance.quantity or 0) if balance else Decimal("0")
    expires_on = None

    if payload.operation_type == "issue":
        if current_quantity < payload.quantity:
            raise ApiError(
                f"{warehouse.name} 的“{item.name}”库存不足，可用 {_number_text(current_quantity)}",
                409,
                "STOCK_INSUFFICIENT",
                "quantity",
                {"available": _number_text(current_quantity)},
            )
        if payload.lot_no:
            lot_quantity, expires_on = _lot_stock(warehouse.id, item.id, payload.lot_no)
            if lot_quantity < payload.quantity:
                raise ApiError(
                    f"批号 {payload.lot_no} 库存不足，可用 {_number_text(lot_quantity)}",
                    409,
                    "LOT_STOCK_INSUFFICIENT",
                    "quantity",
                    {"available": _number_text(lot_quantity)},
                )
        unit_cost = Decimal(balance.average_cost or 0)
        balance.quantity = current_quantity - payload.quantity
        quantity_delta = -payload.quantity
        document_type = "PRODUCTION_ISSUE"
    else:
        outstanding_quantity, outstanding_amount, expires_on = _outstanding_production_issue(
            payload.farm_id,
            warehouse.id,
            item.id,
            payload.lot_no,
            cost_object_type,
            cost_object_id,
            payload.operation_date,
        )
        if outstanding_quantity < payload.quantity:
            raise ApiError(
                f"该使用对象可退“{item.name}”不足，可退 {_number_text(max(outstanding_quantity, Decimal('0')))}",
                409,
                "RETURN_EXCEEDS_ISSUED",
                "quantity",
                {"available": _number_text(max(outstanding_quantity, Decimal("0")))},
            )
        unit_cost = (outstanding_amount / outstanding_quantity).quantize(COST_STEP, rounding=ROUND_HALF_UP)
        if balance is None:
            balance = InventoryBalance(
                farm_id=payload.farm_id,
                warehouse_id=warehouse.id,
                item_id=item.id,
            )
            db.session.add(balance)
        current_cost = Decimal(balance.average_cost or 0)
        new_quantity = current_quantity + payload.quantity
        balance.quantity = new_quantity
        balance.average_cost = (
            ((current_quantity * current_cost) + (payload.quantity * unit_cost)) / new_quantity
        ).quantize(COST_STEP, rounding=ROUND_HALF_UP)
        quantity_delta = payload.quantity
        document_type = "PRODUCTION_RETURN"

    document = StockDocument(
        farm_id=payload.farm_id,
        document_no=payload.document_no,
        document_type=document_type,
        from_warehouse_id=warehouse.id if payload.operation_type == "issue" else None,
        to_warehouse_id=warehouse.id if payload.operation_type == "return" else None,
        source_type=f"MANUAL_{document_type}",
        source_id=None,
        occurred_at=datetime.combine(payload.operation_date, time.min),
        created_by_id=actor.id,
    )
    db.session.add(document)
    try:
        db.session.flush()
        db.session.add(StockMovementLine(
            stock_document_id=document.id,
            warehouse_id=warehouse.id,
            item_id=item.id,
            quantity_delta=quantity_delta,
            unit_cost=unit_cost,
            lot_no=payload.lot_no,
            expires_on=expires_on,
            cost_object_type=cost_object_type,
            cost_object_id=cost_object_id,
        ))
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        existing = _existing_production_operation(payload)
        if existing is not None:
            return existing, False
        raise ApiError("生产领退料过账冲突，请刷新后重试", 409, "PRODUCTION_POST_CONFLICT") from error
    return _production_operation_payload(document), True


def _stock_payload(balance, item, unit, warehouse):
    value = (balance.quantity * balance.average_cost).quantize(MONEY_STEP, rounding=ROUND_HALF_UP)
    return {
        "id": balance.id,
        "farmId": balance.farm_id,
        "warehouseId": warehouse.id,
        "warehouseName": warehouse.name,
        "itemId": item.id,
        "itemCode": item.code,
        "itemName": item.name,
        "unitName": unit.name,
        "quantity": _number_text(balance.quantity),
        "averageCost": _number_text(balance.average_cost),
        "inventoryValue": _money_text(value),
        "safetyStock": _number_text(item.safety_stock),
        "lowStock": balance.quantity <= item.safety_stock,
        "updatedAt": format_datetime(balance.updated_at),
    }


def list_stocks(query, actor):
    get_accessible_farm(query.farm_id, actor)
    base_conditions = [InventoryBalance.farm_id == query.farm_id]
    if query.warehouse_id:
        base_conditions.append(InventoryBalance.warehouse_id == query.warehouse_id)
    if query.keyword:
        base_conditions.append(or_(
            Item.code.contains(query.keyword, autoescape=True),
            Item.name.contains(query.keyword, autoescape=True),
            Warehouse.name.contains(query.keyword, autoescape=True),
        ))
    conditions = [*base_conditions]
    if query.low_stock:
        conditions.append(InventoryBalance.quantity <= Item.safety_stock)
    total = db.session.scalar(
        select(func.count(InventoryBalance.id))
        .join(Item, Item.id == InventoryBalance.item_id)
        .join(Warehouse, Warehouse.id == InventoryBalance.warehouse_id)
        .where(*conditions)
    ) or 0
    rows = db.session.execute(
        select(InventoryBalance, Item, Unit, Warehouse)
        .join(Item, Item.id == InventoryBalance.item_id)
        .join(Unit, Unit.id == Item.unit_id)
        .join(Warehouse, Warehouse.id == InventoryBalance.warehouse_id)
        .where(*conditions)
        .order_by(Warehouse.name, Item.name, Item.id)
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
    ).all()
    summary = db.session.execute(
        select(
            func.count(InventoryBalance.id),
            func.coalesce(func.sum(InventoryBalance.quantity * InventoryBalance.average_cost), 0),
            func.coalesce(func.sum(InventoryBalance.quantity <= Item.safety_stock), 0),
        )
        .join(Item, Item.id == InventoryBalance.item_id)
        .join(Warehouse, Warehouse.id == InventoryBalance.warehouse_id)
        .where(*base_conditions)
    ).one()
    return _paginated(
        [_stock_payload(*row) for row in rows],
        query,
        total,
        summary={
            "itemCount": int(summary[0] or 0),
            "totalValue": _money_text(Decimal(summary[1] or 0)),
            "lowStockCount": int(summary[2] or 0),
        },
    )


def _ledger_payload(movement, document, item, unit, warehouse):
    amount = abs(movement.quantity_delta * movement.unit_cost).quantize(MONEY_STEP, rounding=ROUND_HALF_UP)
    return {
        "id": movement.id,
        "documentNo": document.document_no,
        "documentType": document.document_type,
        "sourceType": document.source_type,
        "sourceId": document.source_id,
        "occurredAt": format_datetime(document.occurred_at),
        "warehouseId": warehouse.id,
        "warehouseName": warehouse.name,
        "itemId": item.id,
        "itemCode": item.code,
        "itemName": item.name,
        "unitName": unit.name,
        "quantityDelta": _number_text(movement.quantity_delta),
        "unitCost": _number_text(movement.unit_cost),
        "amount": _money_text(amount),
        "lotNo": movement.lot_no,
        "expiresOn": movement.expires_on.isoformat() if movement.expires_on else None,
        "costObjectType": movement.cost_object_type,
        "costObjectId": movement.cost_object_id,
    }


def list_stock_ledger(query, actor):
    get_accessible_farm(query.farm_id, actor)
    conditions = [StockDocument.farm_id == query.farm_id, StockDocument.status == "POSTED"]
    if query.warehouse_id:
        conditions.append(StockMovementLine.warehouse_id == query.warehouse_id)
    if query.item_id:
        conditions.append(StockMovementLine.item_id == query.item_id)
    if query.keyword:
        conditions.append(or_(
            StockDocument.document_no.contains(query.keyword, autoescape=True),
            Item.code.contains(query.keyword, autoescape=True),
            Item.name.contains(query.keyword, autoescape=True),
        ))
    if query.date_from:
        conditions.append(StockDocument.occurred_at >= datetime.combine(query.date_from, time.min))
    if query.date_to:
        conditions.append(StockDocument.occurred_at < datetime.combine(query.date_to + timedelta(days=1), time.min))
    base = (
        select(StockMovementLine.id)
        .join(StockDocument, StockDocument.id == StockMovementLine.stock_document_id)
        .join(Item, Item.id == StockMovementLine.item_id)
        .where(*conditions)
    )
    total = db.session.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.session.execute(
        select(StockMovementLine, StockDocument, Item, Unit, Warehouse)
        .join(StockDocument, StockDocument.id == StockMovementLine.stock_document_id)
        .join(Item, Item.id == StockMovementLine.item_id)
        .join(Unit, Unit.id == Item.unit_id)
        .join(Warehouse, Warehouse.id == StockMovementLine.warehouse_id)
        .where(*conditions)
        .order_by(StockDocument.occurred_at.desc(), StockMovementLine.id.desc())
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
    ).all()
    return _paginated([_ledger_payload(*row) for row in rows], query, total)


def reconcile_inventory(farm_id=None):
    movement_statement = (
        select(
            StockDocument.farm_id,
            StockMovementLine.warehouse_id,
            StockMovementLine.item_id,
            func.sum(StockMovementLine.quantity_delta),
        )
        .join(StockDocument, StockDocument.id == StockMovementLine.stock_document_id)
        .where(StockDocument.status == "POSTED")
        .group_by(StockDocument.farm_id, StockMovementLine.warehouse_id, StockMovementLine.item_id)
    )
    balance_statement = select(
        InventoryBalance.farm_id,
        InventoryBalance.warehouse_id,
        InventoryBalance.item_id,
        InventoryBalance.quantity,
    )
    if farm_id:
        movement_statement = movement_statement.where(StockDocument.farm_id == farm_id)
        balance_statement = balance_statement.where(InventoryBalance.farm_id == farm_id)
    movement_totals = {
        (row[0], row[1], row[2]): Decimal(row[3] or 0)
        for row in db.session.execute(movement_statement)
    }
    balances = {
        (row[0], row[1], row[2]): Decimal(row[3] or 0)
        for row in db.session.execute(balance_statement)
    }
    discrepancies = []
    for key in sorted(set(movement_totals) | set(balances)):
        movement_quantity = movement_totals.get(key, Decimal("0"))
        balance_quantity = balances.get(key, Decimal("0"))
        if movement_quantity != balance_quantity:
            discrepancies.append({
                "farmId": key[0],
                "warehouseId": key[1],
                "itemId": key[2],
                "movementQuantity": _number_text(movement_quantity),
                "balanceQuantity": _number_text(balance_quantity),
                "difference": _number_text(balance_quantity - movement_quantity),
            })
    return discrepancies
