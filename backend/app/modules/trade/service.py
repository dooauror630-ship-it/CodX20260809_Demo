from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from math import ceil
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from ...core.errors import ApiError
from ...extensions import db
from ..auth.service import format_datetime
from ..farm.service import get_accessible_farm
from ..inventory.models import InventoryBalance, Item, StockDocument, StockMovementLine, Warehouse
from ..inventory.purchase_service import _require_write_access
from .models import Customer, Payment, SalesOrder, SalesOrderLine


def _money(value):
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def customer_payload(c):
    return {
        "id": c.id,
        "farmId": c.farm_id,
        "code": c.code,
        "name": c.name,
        "contact": c.contact,
        "phone": c.phone,
        "address": c.address,
        "isActive": c.is_active,
        "createdAt": format_datetime(c.created_at),
    }


def list_customers(query, actor):
    get_accessible_farm(query.farm_id, actor)
    conditions = [Customer.farm_id == query.farm_id]
    if query.keyword:
        conditions.append(
            or_(
                Customer.code.contains(query.keyword, autoescape=True),
                Customer.name.contains(query.keyword, autoescape=True),
            )
        )
    total = db.session.scalar(select(func.count(Customer.id)).where(*conditions)) or 0
    rows = db.session.scalars(
        select(Customer)
        .where(*conditions)
        .order_by(Customer.name, Customer.id)
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
    ).all()
    return {
        "items": [customer_payload(c) for c in rows],
        "pagination": {
            "page": query.page,
            "pageSize": query.page_size,
            "total": total,
            "totalPages": ceil(total / query.page_size) if total else 0,
        },
    }


def create_customer(payload, actor):
    _require_write_access(payload.farm_id, actor)
    c = db.session.scalar(select(Customer).where(Customer.farm_id == payload.farm_id, Customer.code == payload.code))
    if c:
        return customer_payload(c), False
    c = Customer(
        farm_id=payload.farm_id,
        code=payload.code,
        name=payload.name,
        contact=payload.contact,
        phone=payload.phone,
        address=payload.address,
        created_by_id=actor.id,
        updated_by_id=actor.id,
    )
    db.session.add(c)
    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        raise ApiError("客户编号已存在", 409, "CUSTOMER_CODE_EXISTS", "code") from e
    return customer_payload(c), True


def _validate_sales_refs(payload, actor):
    _require_write_access(payload.farm_id, actor)
    customer = db.session.get(Customer, payload.customer_id)
    warehouse = db.session.get(Warehouse, payload.warehouse_id)
    if not customer or customer.farm_id != payload.farm_id:
        raise ApiError("客户不属于当前农场", 409, "CUSTOMER_FARM_MISMATCH")
    if not warehouse or warehouse.farm_id != payload.farm_id:
        raise ApiError("仓库不属于当前农场", 409, "WAREHOUSE_FARM_MISMATCH")
    items = {}
    for line in payload.lines:
        item = db.session.get(Item, line.item_id)
        if not item or item.farm_id != payload.farm_id:
            raise ApiError("物料不属于当前农场", 409, "ITEM_FARM_MISMATCH")
        items[item.id] = item
    return customer, warehouse, items


def sales_payload(order, customer, lines=None):
    payload = {
        "id": order.id,
        "farmId": order.farm_id,
        "orderNo": order.order_no,
        "customerId": order.customer_id,
        "customerName": customer.name,
        "warehouseId": order.warehouse_id,
        "saleDate": order.sale_date.isoformat(),
        "status": order.status,
        "totalAmount": f"{order.total_amount:.2f}",
        "receivedAmount": f"{order.received_amount:.2f}",
        "notes": order.notes,
        "postedAt": format_datetime(order.posted_at),
    }
    if lines is not None:
        payload["lines"] = [{"id": line.id, "itemId": line.item_id, "quantity": str(line.quantity), "unitPrice": f"{line.unit_price:.4f}", "amount": f"{line.amount:.2f}", "unitCost": f"{line.unit_cost:.4f}"} for line in lines]
    return payload


def create_sales_order(payload, actor):
    customer, warehouse, items = _validate_sales_refs(payload, actor)
    existing = db.session.scalar(
        select(SalesOrder).where(SalesOrder.farm_id == payload.farm_id, SalesOrder.order_no == payload.order_no)
    )
    if existing:
        return sales_payload(existing, customer), False
    total = sum((_money(line.quantity * line.unit_price) for line in payload.lines), Decimal("0"))
    order = SalesOrder(
        farm_id=payload.farm_id,
        order_no=payload.order_no,
        customer_id=customer.id,
        warehouse_id=warehouse.id,
        sale_date=payload.sale_date,
        total_amount=total,
        notes=payload.notes,
        created_by_id=actor.id,
    )
    db.session.add(order)
    db.session.flush()
    for line in payload.lines:
        db.session.add(
            SalesOrderLine(
                sales_order_id=order.id,
                item_id=line.item_id,
                quantity=line.quantity,
                unit_price=line.unit_price,
                amount=_money(line.quantity * line.unit_price),
            )
        )
    db.session.commit()
    return sales_payload(order, customer), True


def list_sales_orders(query, actor):
    get_accessible_farm(query.farm_id, actor)
    conditions = [SalesOrder.farm_id == query.farm_id]
    if query.status != "all":
        conditions.append(SalesOrder.status == query.status)
    rows = db.session.execute(
        select(SalesOrder, Customer)
        .join(Customer, Customer.id == SalesOrder.customer_id)
        .where(*conditions)
        .order_by(SalesOrder.sale_date.desc(), SalesOrder.id.desc())
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
    ).all()
    total = db.session.scalar(select(func.count(SalesOrder.id)).where(*conditions)) or 0
    return {
        "items": [sales_payload(o, c) for o, c in rows],
        "pagination": {
            "page": query.page,
            "pageSize": query.page_size,
            "total": total,
            "totalPages": ceil(total / query.page_size) if total else 0,
        },
    }


def post_sales_order(order_id, actor):
    order = db.session.scalar(select(SalesOrder).where(SalesOrder.id == order_id).with_for_update())
    if not order:
        raise ApiError("销售单不存在", 404, "SALES_ORDER_NOT_FOUND")
    _require_write_access(order.farm_id, actor)
    if order.status == "POSTED":
        return sales_payload(order, db.session.get(Customer, order.customer_id))
    lines = db.session.scalars(select(SalesOrderLine).where(SalesOrderLine.sales_order_id == order.id)).all()
    balances = {}
    for line in lines:
        balance = db.session.scalar(
            select(InventoryBalance)
            .where(InventoryBalance.warehouse_id == order.warehouse_id, InventoryBalance.item_id == line.item_id)
            .with_for_update()
        )
        if not balance or balance.quantity < line.quantity:
            raise ApiError("库存不足，不能销售过账", 409, "SALES_STOCK_INSUFFICIENT")
        balances[line.id] = balance
        line.unit_cost = balance.average_cost
        balance.quantity -= line.quantity
    document = StockDocument(
        farm_id=order.farm_id,
        document_no=f"SO-{order.order_no}",
        document_type="SALES_ISSUE",
        status="POSTED",
        source_type="SALES_ORDER",
        source_id=order.id,
        occurred_at=datetime.combine(order.sale_date, datetime.min.time()),
        created_by_id=actor.id,
    )
    db.session.add(document)
    db.session.flush()
    for line in lines:
        db.session.add(
            StockMovementLine(
                stock_document_id=document.id,
                warehouse_id=order.warehouse_id,
                item_id=line.item_id,
                quantity_delta=-line.quantity,
                unit_cost=line.unit_cost,
            )
        )
    order.status = "POSTED"
    order.posted_at = datetime.now()
    order.posted_by_id = actor.id
    db.session.commit()
    return sales_payload(order, db.session.get(Customer, order.customer_id))


def create_payment(payload, actor):
    _require_write_access(payload.farm_id, actor)
    existing = db.session.scalar(
        select(Payment).where(Payment.farm_id == payload.farm_id, Payment.payment_no == payload.payment_no)
    )
    if existing:
        return {"id": existing.id, "paymentNo": existing.payment_no, "amount": f"{existing.amount:.2f}"}, False
    if payload.sales_order_id:
        order = db.session.get(SalesOrder, payload.sales_order_id)
        if not order or order.farm_id != payload.farm_id or order.status != "POSTED":
            raise ApiError("收款必须关联已过账销售单", 409, "PAYMENT_ORDER_INVALID")
        if order.received_amount + payload.amount > order.total_amount:
            raise ApiError("收款不能超过销售应收", 409, "PAYMENT_EXCEEDS_RECEIVABLE")
        order.received_amount += payload.amount
    p = Payment(
        farm_id=payload.farm_id,
        payment_no=payload.payment_no,
        direction="IN",
        business_date=payload.business_date,
        amount=payload.amount,
        method=payload.method,
        customer_id=payload.customer_id,
        sales_order_id=payload.sales_order_id,
        notes=payload.notes,
        created_by_id=actor.id,
    )
    db.session.add(p)
    db.session.commit()
    return {"id": p.id, "paymentNo": p.payment_no, "amount": f"{p.amount:.2f}"}, True


def trade_summary(farm_id, actor):
    get_accessible_farm(farm_id, actor)
    revenue = (
        db.session.scalar(
            select(func.coalesce(func.sum(SalesOrder.total_amount), 0)).where(
                SalesOrder.farm_id == farm_id, SalesOrder.status == "POSTED"
            )
        )
        or 0
    )
    cost = db.session.scalar(
        select(func.coalesce(func.sum(SalesOrderLine.quantity * SalesOrderLine.unit_cost), 0))
        .join(SalesOrder, SalesOrder.id == SalesOrderLine.sales_order_id)
        .where(SalesOrder.farm_id == farm_id, SalesOrder.status == "POSTED")
    ) or 0
    received = (
        db.session.scalar(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.farm_id == farm_id, Payment.direction == "IN"
            )
        )
        or 0
    )
    return {
        "postedSalesAmount": f"{Decimal(revenue):.2f}",
        "salesCost": f"{Decimal(cost):.2f}",
        "grossProfit": f"{Decimal(revenue) - Decimal(cost):.2f}",
        "receivedAmount": f"{Decimal(received):.2f}",
        "cashNetInflow": f"{Decimal(received):.2f}",
        "receivableAmount": f"{Decimal(revenue) - Decimal(received):.2f}",
    }
