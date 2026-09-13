from flask import Blueprint, current_app, g, request

from ...core.errors import ApiError, success_response
from ...core.security import login_required
from ..auth.schemas import parse_payload
from ..inventory.purchase_schemas import ConfirmPurchasePayload, CreatePurchasePayload
from ..inventory.inventory_count_schemas import CreateInventoryCountPayload
from .schemas import AssistantInventoryCountUpdatePayload, AssistantStockTransferDraftPayload
from .service import (
    agent_context,
    agent_session_required,
    create_agent_session_token,
    internal_current_user,
    internal_farms,
    internal_inventory_summary,
    internal_livestock_summary,
    internal_trade_summary,
    internal_purchase_draft,
    internal_purchase_confirm,
    internal_purchase_options,
    internal_inventory_count_draft,
    internal_inventory_count_confirm,
    internal_inventory_count_detail,
    internal_inventory_count_update,
    internal_users,
    internal_stock_transfer_draft,
    internal_stock_transfer_confirm,
)


assistant_bp = Blueprint("assistant", __name__)


def _farm_id():
    farm_id = request.args.get("farmId", type=int)
    if farm_id is None or farm_id <= 0:
        raise ApiError("farmId 必须是正整数", 400, "FARM_ID_INVALID", "farmId")
    return farm_id


@assistant_bp.get("/context")
@login_required
def context():
    return success_response(agent_context(g.current_user))


@assistant_bp.post("/session")
@login_required
def session_token():
    return success_response({
        "token": create_agent_session_token(g.current_user),
        "expiresIn": current_app.config["AGENT_SESSION_MAX_AGE"],
        "context": agent_context(g.current_user),
    })


@assistant_bp.get("/internal/context")
@agent_session_required
def internal_context():
    return success_response(agent_context(g.agent_user))


@assistant_bp.get("/internal/farms")
@agent_session_required
def farms():
    return success_response(internal_farms(g.agent_user))


@assistant_bp.get("/internal/current-user")
@agent_session_required
def current_user():
    return success_response(internal_current_user(g.agent_user))


@assistant_bp.get("/internal/purchase-options")
@agent_session_required
def purchase_options():
    return success_response(internal_purchase_options(_farm_id(), g.agent_user))


@assistant_bp.post("/internal/purchase-draft")
@agent_session_required
def purchase_draft():
    payload = parse_payload(CreatePurchasePayload, request.get_json(silent=True), "采购草稿格式错误")
    return success_response(internal_purchase_draft(payload, g.agent_user))


@assistant_bp.post("/internal/purchase-confirm")
@agent_session_required
def purchase_confirm():
    payload = parse_payload(ConfirmPurchasePayload, request.get_json(silent=True), "采购确认格式错误")
    return success_response(internal_purchase_confirm(payload.confirmation_token, g.agent_user))


@assistant_bp.post("/internal/stock-transfer-draft")
@agent_session_required
def stock_transfer_draft():
    payload = parse_payload(AssistantStockTransferDraftPayload, request.get_json(silent=True), "调拨草稿格式错误")
    return success_response(internal_stock_transfer_draft(payload, g.agent_user))


@assistant_bp.post("/internal/stock-transfer-confirm")
@agent_session_required
def stock_transfer_confirm():
    payload = parse_payload(ConfirmPurchasePayload, request.get_json(silent=True), "调拨确认格式错误")
    return success_response(internal_stock_transfer_confirm(payload.confirmation_token, g.agent_user))


@assistant_bp.post("/internal/inventory-count-draft")
@agent_session_required
def inventory_count_draft():
    payload = parse_payload(CreateInventoryCountPayload, request.get_json(silent=True), "盘点草稿格式错误")
    return success_response(internal_inventory_count_draft(payload, g.agent_user))


@assistant_bp.get("/internal/inventory-counts/<int:count_id>")
@agent_session_required
def inventory_count_detail_route(count_id):
    return success_response(internal_inventory_count_detail(count_id, g.agent_user))


@assistant_bp.post("/internal/inventory-count-update")
@agent_session_required
def inventory_count_update():
    payload = parse_payload(
        AssistantInventoryCountUpdatePayload,
        request.get_json(silent=True),
        "盘点草稿明细格式错误",
    )
    return success_response(internal_inventory_count_update(payload, g.agent_user))


@assistant_bp.post("/internal/inventory-count-confirm")
@agent_session_required
def inventory_count_confirm():
    payload = parse_payload(ConfirmPurchasePayload, request.get_json(silent=True), "盘点确认格式错误")
    return success_response(internal_inventory_count_confirm(payload.confirmation_token, g.agent_user))


@assistant_bp.get("/internal/users")
@agent_session_required
def users():
    return success_response(internal_users(g.agent_user))


@assistant_bp.get("/internal/inventory-summary")
@agent_session_required
def inventory():
    return success_response(internal_inventory_summary(_farm_id(), g.agent_user))


@assistant_bp.get("/internal/livestock-summary")
@agent_session_required
def livestock():
    return success_response(internal_livestock_summary(_farm_id(), g.agent_user))


@assistant_bp.get("/internal/trade-summary")
@agent_session_required
def trade():
    return success_response(internal_trade_summary(_farm_id(), g.agent_user))
