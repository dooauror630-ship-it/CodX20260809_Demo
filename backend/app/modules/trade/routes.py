from flask import Blueprint, g, request
from ...core.errors import success_response
from ...core.security import login_required
from ..auth.schemas import parse_payload
from .schemas import (
    CustomerListQuery,
    CreateCustomerPayload,
    CreateSalesOrderPayload,
    SalesListQuery,
    CreatePaymentPayload,
    CreateSalesReturnPayload,
)
from .service import (
    create_customer,
    create_payment,
    create_sales_order,
    list_customers,
    list_sales_orders,
    post_sales_order,
    trade_summary,
    trade_profit,
    sales_order_detail,
    create_sales_return,
)

trade_bp = Blueprint("trade", __name__)


@trade_bp.get("/customers")
@login_required
def customers():
    return success_response(
        list_customers(parse_payload(CustomerListQuery, request.args.to_dict(), "客户筛选条件格式错误"), g.current_user)
    )


@trade_bp.post("/customers")
@login_required
def add_customer():
    customer, created = create_customer(
        parse_payload(CreateCustomerPayload, request.get_json(silent=True), "客户信息格式错误"), g.current_user
    )
    return success_response(
        {"customer": customer}, "客户已创建" if created else "该客户已存在", 201 if created else 200
    )


@trade_bp.get("/sales-orders")
@login_required
def sales_orders():
    return success_response(
        list_sales_orders(
            parse_payload(SalesListQuery, request.args.to_dict(), "销售单筛选条件格式错误"), g.current_user
        )
    )


@trade_bp.post("/sales-orders")
@login_required
def add_sales_order():
    order, created = create_sales_order(
        parse_payload(CreateSalesOrderPayload, request.get_json(silent=True), "销售单信息格式错误"), g.current_user
    )
    return success_response({"order": order}, "销售单已创建" if created else "该销售单已存在", 201 if created else 200)


@trade_bp.post("/sales-orders/<int:order_id>/post")
@login_required
def post_sales(order_id):
    return success_response({"order": post_sales_order(order_id, g.current_user)}, "销售单已过账")


@trade_bp.post("/payments")
@login_required
def payments():
    payment, created = create_payment(
        parse_payload(CreatePaymentPayload, request.get_json(silent=True), "收款信息格式错误"), g.current_user
    )
    return success_response({"payment": payment}, "收款已登记" if created else "该收款已存在", 201 if created else 200)


@trade_bp.get("/sales-orders/<int:order_id>")
@login_required
def sales_order_detail_route(order_id):
    return success_response({"order": sales_order_detail(order_id, g.current_user)})


@trade_bp.post("/sales-returns")
@login_required
def sales_returns():
    payload = parse_payload(CreateSalesReturnPayload, request.get_json(silent=True), "销售退货信息格式错误")
    result, created = create_sales_return(payload, g.current_user)
    return success_response({"return": result}, "销售退货已登记" if created else "该退货单已存在", 201 if created else 200)


@trade_bp.get("/trade-summary")
@login_required
def summary():
    return success_response(trade_summary(request.args.get("farmId", type=int), g.current_user))


@trade_bp.get("/trade-profit")
@login_required
def profit():
    return success_response({"items": trade_profit(request.args.get("farmId", type=int), g.current_user)})
