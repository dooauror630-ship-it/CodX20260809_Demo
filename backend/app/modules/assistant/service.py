import json
import secrets
from datetime import datetime
from decimal import Decimal
from functools import wraps

from flask import current_app, g, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import select

from ...core.errors import ApiError
from ...extensions import db
from ..agent.service import _farm_payload, inventory_summary, livestock_summary
from ..admin.schemas import UserListQuery
from ..admin.service import list_users
from ..auth.models import User
from ..auth.service import user_payload
from ..farm.models import Farm, FarmUser
from ..farm.service import get_accessible_farm
from ..inventory.models import InventoryBalance, InventoryCount, Item, PurchaseOrder, StockDocument, StockMovementLine, Supplier, Warehouse
from ..inventory.inventory_count_schemas import CreateInventoryCountPayload, InventoryCountActionPayload
from ..inventory.inventory_count_schemas import UpdateInventoryCountPayload
from ..inventory.inventory_count_service import (
    create_inventory_count,
    inventory_count_detail,
    post_inventory_count,
    update_inventory_count,
)
from ..inventory.purchase_schemas import PurchaseActionPayload
from ..inventory.purchase_service import (
    _active_stock_item,
    _active_warehouse,
    _lot_stock,
    _number_text,
    _require_write_access,
    _stock_transfer_payload,
    create_purchase,
    post_purchase,
    purchase_detail,
)
from ..workflow.models import AuditLog
from .models import AgentConfirmationNonce


AGENT_SESSION_SALT = "agri-harness-agent-session"
AGENT_CONFIRMATION_SALT = "agri-harness-write-confirmation"
ROLE_LEVELS = {"viewer": 1, "operator": 2, "manager": 3, "admin": 4}

# Prompts are not a permission boundary; every draft still passes backend
# role, farm, and business validation.
TOOL_CATALOG = (
    {
        "name": "agri_list_farms",
        "label": "查询可访问农场",
        "mode": "read",
        "minRole": "viewer",
        "status": "enabled",
    },
    {
        "name": "agri_current_user",
        "label": "查询当前登录用户",
        "mode": "read",
        "minRole": "viewer",
        "status": "enabled",
    },
    {
        "name": "agri_purchase_options",
        "label": "查询采购基础选项",
        "mode": "read",
        "minRole": "viewer",
        "status": "enabled",
    },
    {
        "name": "agri_list_users",
        "label": "查询系统用户列表",
        "mode": "read",
        "minRole": "admin",
        "status": "enabled",
    },
    {
        "name": "agri_inventory_summary",
        "label": "查询库存概览",
        "mode": "read",
        "minRole": "viewer",
        "status": "enabled",
    },
    {
        "name": "agri_livestock_summary",
        "label": "查询养殖概览",
        "mode": "read",
        "minRole": "viewer",
        "status": "enabled",
    },
    {
        "name": "agri_create_draft",
        "label": "创建业务草稿",
        "mode": "draft",
        "minRole": "operator",
        "status": "enabled",
    },
    {
        "name": "agri_confirm_write",
        "label": "确认业务写入",
        "mode": "write",
        "minRole": "manager",
        "status": "enabled",
    },
    {
        "name": "agri_create_inventory_count_draft",
        "label": "创建盘点草稿",
        "mode": "draft",
        "minRole": "operator",
        "status": "enabled",
    },
    {
        "name": "agri_inventory_count_detail",
        "label": "查询盘点草稿",
        "mode": "read",
        "minRole": "viewer",
        "status": "enabled",
    },
    {
        "name": "agri_update_inventory_count_draft",
        "label": "更新盘点草稿",
        "mode": "draft",
        "minRole": "operator",
        "status": "enabled",
    },
    {
        "name": "agri_confirm_inventory_count",
        "label": "确认盘点过账",
        "mode": "write",
        "minRole": "manager",
        "status": "enabled",
    },
    {
        "name": "agri_create_stock_transfer_draft",
        "label": "创建仓库调拨草稿",
        "mode": "draft",
        "minRole": "operator",
        "status": "enabled",
    },
    {
        "name": "agri_confirm_stock_transfer",
        "label": "确认仓库调拨过账",
        "mode": "write",
        "minRole": "manager",
        "status": "enabled",
    },
)


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=AGENT_SESSION_SALT)


def _confirmation_serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=AGENT_CONFIRMATION_SALT)


def create_agent_session_token(user):
    return _serializer().dumps({
        "sub": int(user.id),
        "aud": "agri-harness",
        "v": 1,
        "userVersion": user.updated_at.isoformat() if user.updated_at else None,
    })


def resolve_agent_session_token(token):
    try:
        payload = _serializer().loads(token, max_age=current_app.config["AGENT_SESSION_MAX_AGE"])
    except SignatureExpired as error:
        raise ApiError("智能体会话已过期", 401, "AGENT_SESSION_EXPIRED") from error
    except BadSignature as error:
        raise ApiError("智能体会话无效", 401, "AGENT_SESSION_INVALID") from error

    if payload.get("aud") != "agri-harness" or not isinstance(payload.get("sub"), int):
        raise ApiError("智能体会话无效", 401, "AGENT_SESSION_INVALID")
    user = db.session.get(User, payload["sub"])
    if user is None or not user.is_active:
        raise ApiError("用户不存在或已停用", 401, "AGENT_SESSION_INVALID")
    current_version = user.updated_at.isoformat() if user.updated_at else None
    if payload.get("userVersion") != current_version:
        raise ApiError("智能体会话已失效，请重新建立会话", 401, "AGENT_SESSION_REVOKED")
    return user


def _role_level(role):
    return ROLE_LEVELS.get(role, 0)


def tools_for_role(role):
    level = _role_level(role)
    return [
        tool
        for tool in TOOL_CATALOG
        if tool["status"] == "enabled" and level >= _role_level(tool["minRole"])
    ]


def _farm_rows(user):
    if user.role == "admin":
        rows = db.session.scalars(
            select(Farm).where(Farm.is_active.is_(True)).order_by(Farm.name, Farm.id)
        ).all()
        return [(_farm_payload(farm), "admin") for farm in rows]

    rows = db.session.execute(
        select(Farm, FarmUser.role_code)
        .join(FarmUser, FarmUser.farm_id == Farm.id)
        .where(
            Farm.is_active.is_(True),
            FarmUser.user_id == user.id,
            FarmUser.is_active.is_(True),
        )
        .order_by(Farm.name, Farm.id)
    ).all()
    return [(_farm_payload(farm), role) for farm, role in rows]


def agent_context(user):
    farms = []
    farm_rows = _farm_rows(user)
    roles = {"admin"} if user.role == "admin" else {role for _farm, role in farm_rows}
    for farm, farm_role in farm_rows:
        effective_role = user.role if user.role == "admin" else farm_role
        farms.append({
            **farm,
            "accessRole": farm_role,
            "tools": tools_for_role(effective_role),
        })
    return {
        "user": user_payload(user),
        "tools": [
            tool
            for tool in TOOL_CATALOG
            if tool["status"] == "enabled"
            and any(_role_level(role) >= _role_level(tool["minRole"]) for role in roles)
        ],
        "farms": farms,
        "writePolicy": {
            "enabled": any(_role_level(role) >= _role_level("manager") for role in roles),
        "scope": ["purchase-post", "inventory-count-post", "stock-transfer-post"],
        "reason": "仅支持通过短时确认挑战过账采购、盘点或调拨草稿",
        },
    }


def agent_session_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            raise ApiError("缺少智能体会话令牌", 401, "AGENT_SESSION_REQUIRED")
        g.agent_user = resolve_agent_session_token(header[7:])
        return view(*args, **kwargs)

    return wrapped


def internal_farms(user):
    return {"farms": [farm for farm, _role in _farm_rows(user)]}


def internal_current_user(user):
    return {"user": user_payload(user)}


def internal_users(user):
    if user.role != "admin":
        raise ApiError("当前用户无权查询系统用户列表", 403, "AGENT_TOOL_FORBIDDEN")
    return list_users(UserListQuery(page=1, page_size=100))


def internal_purchase_options(farm_id, user):
    farm, _role = get_accessible_farm(farm_id, user)
    suppliers = db.session.scalars(
        select(Supplier).where(Supplier.farm_id == farm.id, Supplier.is_active.is_(True))
        .order_by(Supplier.name, Supplier.id).limit(100)
    ).all()
    warehouses = db.session.scalars(
        select(Warehouse).where(Warehouse.farm_id == farm.id, Warehouse.is_active.is_(True))
        .order_by(Warehouse.name, Warehouse.id).limit(100)
    ).all()
    items = db.session.execute(
        select(Item).where(Item.farm_id == farm.id, Item.is_active.is_(True))
        .order_by(Item.name, Item.id).limit(200)
    ).scalars().all()
    return {
        "farm": _farm_payload(farm),
        "suppliers": [{"id": item.id, "code": item.code, "name": item.name} for item in suppliers],
        "warehouses": [{"id": item.id, "code": item.code, "name": item.name} for item in warehouses],
        "items": [{
            "id": item.id,
            "code": item.code,
            "name": item.name,
            "lotTracking": item.lot_tracking,
        } for item in items],
    }


def internal_purchase_draft(payload, user):
    existing = db.session.scalar(
        select(PurchaseOrder).where(
            PurchaseOrder.farm_id == payload.farm_id,
            PurchaseOrder.order_no == payload.order_no,
        )
    )
    if existing is not None:
        get_accessible_farm(existing.farm_id, user)
        if existing.status == "DRAFT" and existing.created_by_id == user.id:
            draft = purchase_detail(existing.id, user)
            return {
                "draft": draft,
                "created": False,
                "requiresConfirmation": True,
                "confirmationToken": create_write_confirmation_token(user, draft, "purchase-post", "purchaseId"),
            }
        raise ApiError("该农场内采购单号已存在", 409, "PURCHASE_NO_EXISTS", "orderNo")

    draft = create_purchase(payload, user)
    db.session.add(AuditLog(
        farm_id=payload.farm_id,
        actor_id=user.id,
        action="CREATE_DRAFT",
        resource_type="PURCHASE_ORDER",
        resource_id=draft["id"],
        detail=json.dumps({"orderNo": draft["orderNo"], "source": "assistant"}, ensure_ascii=False),
    ))
    db.session.commit()
    return {
        "draft": draft,
        "created": True,
        "requiresConfirmation": True,
        "confirmationToken": create_write_confirmation_token(user, draft, "purchase-post", "purchaseId"),
    }


def create_write_confirmation_token(user, draft, action, resource_key):
    return _confirmation_serializer().dumps({
        "sub": int(user.id),
        "aud": "agri-write-confirmation",
        "action": action,
        "farmId": int(draft["farmId"]),
        resource_key: int(draft["id"]),
        "version": int(draft["version"]),
        "nonce": secrets.token_urlsafe(18),
        "userVersion": user.updated_at.isoformat() if user.updated_at else None,
    })


def resolve_write_confirmation_token(token):
    try:
        payload = _confirmation_serializer().loads(
            token,
            max_age=current_app.config["AGENT_CONFIRMATION_MAX_AGE"],
        )
    except SignatureExpired as error:
        raise ApiError("确认挑战已过期，请重新生成草稿确认", 401, "AGENT_CONFIRMATION_EXPIRED") from error
    except BadSignature as error:
        raise ApiError("确认挑战无效", 401, "AGENT_CONFIRMATION_INVALID") from error
    if (
        payload.get("aud") != "agri-write-confirmation"
        or payload.get("action") not in {"purchase-post", "inventory-count-post", "stock-transfer-post"}
        or not all(isinstance(payload.get(key), int) for key in ("sub", "farmId", "version"))
        or not isinstance(payload.get("nonce"), str)
        or not 20 <= len(payload["nonce"]) <= 128
    ):
        raise ApiError("确认挑战无效", 401, "AGENT_CONFIRMATION_INVALID")
    return payload


def _consume_confirmation_nonce(challenge, user, action, resource_id):
    existing = db.session.scalar(
        select(AgentConfirmationNonce)
        .where(AgentConfirmationNonce.nonce == challenge["nonce"])
        .with_for_update()
    )
    if existing is not None:
        raise ApiError("确认挑战已被使用", 409, "AGENT_CONFIRMATION_REPLAYED")
    db.session.add(AgentConfirmationNonce(
        nonce=challenge["nonce"],
        user_id=user.id,
        farm_id=challenge["farmId"],
        action=action,
        resource_id=resource_id,
        used_at=datetime.now(),
    ))
    db.session.flush()


def internal_purchase_confirm(confirmation_token, user):
    challenge = resolve_write_confirmation_token(confirmation_token)
    if challenge.get("action") != "purchase-post" or not isinstance(challenge.get("purchaseId"), int):
        raise ApiError("确认挑战无效", 401, "AGENT_CONFIRMATION_INVALID")
    if challenge["sub"] != user.id:
        raise ApiError("确认挑战不属于当前用户", 403, "AGENT_CONFIRMATION_OWNER_REQUIRED")
    current_version = user.updated_at.isoformat() if user.updated_at else None
    if challenge.get("userVersion") != current_version:
        raise ApiError("确认挑战已失效，请重新生成草稿确认", 401, "AGENT_CONFIRMATION_REVOKED")
    order = db.session.scalar(
        select(PurchaseOrder).where(PurchaseOrder.id == challenge["purchaseId"]).with_for_update()
    )
    if order is None:
        raise ApiError("采购单不存在", 404, "PURCHASE_NOT_FOUND")
    if order.farm_id != challenge["farmId"]:
        raise ApiError("确认挑战与采购单不匹配", 409, "AGENT_CONFIRMATION_MISMATCH")
    _farm, farm_role = get_accessible_farm(order.farm_id, user)
    if user.role != "admin" and farm_role != "manager":
        raise ApiError("仅管理员或农场负责人可以确认采购过账", 403, "AGENT_CONFIRMATION_FORBIDDEN")
    if order.status == "POSTED":
        db.session.add(AuditLog(
            farm_id=order.farm_id,
            actor_id=user.id,
            action="CONFIRM_REPLAY",
            resource_type="PURCHASE_ORDER",
            resource_id=order.id,
            detail=json.dumps({"orderNo": order.order_no, "source": "assistant", "action": "purchase-post", "replay": True}, ensure_ascii=False),
        ))
        db.session.commit()
        return {"purchase": purchase_detail(order.id, user), "confirmed": False, "alreadyPosted": True}
    if order.status != "DRAFT":
        raise ApiError("采购草稿当前状态不能确认", 409, "PURCHASE_NOT_CONFIRMABLE")
    if order.version != challenge["version"]:
        raise ApiError("采购草稿已被更新，请重新生成确认挑战", 409, "PURCHASE_VERSION_CONFLICT")
    _consume_confirmation_nonce(challenge, user, "purchase-post", order.id)
    purchase = post_purchase(order.id, PurchaseActionPayload(version=challenge["version"]), user)
    db.session.add(AuditLog(
        farm_id=order.farm_id,
        actor_id=user.id,
        action="CONFIRM_WRITE",
        resource_type="PURCHASE_ORDER",
        resource_id=order.id,
        detail=json.dumps({"orderNo": order.order_no, "source": "assistant", "action": "purchase-post"}, ensure_ascii=False),
    ))
    db.session.commit()
    return {"purchase": purchase, "confirmed": True, "alreadyPosted": False}


def internal_inventory_count_draft(payload: CreateInventoryCountPayload, user):
    existing = db.session.scalar(
        select(InventoryCount).where(
            InventoryCount.farm_id == payload.farm_id,
            InventoryCount.count_no == payload.count_no,
        )
    )
    if existing is not None:
        get_accessible_farm(existing.farm_id, user)
        if existing.status == "DRAFT" and existing.created_by_id == user.id:
            draft = inventory_count_detail(existing.id, user)
            return {
                "draft": draft,
                "created": False,
                "requiresConfirmation": True,
                "confirmationToken": create_write_confirmation_token(
                    user, draft, "inventory-count-post", "inventoryCountId"
                ),
            }
        raise ApiError("该农场内盘点单号已存在", 409, "INVENTORY_COUNT_NO_EXISTS", "countNo")

    draft = create_inventory_count(payload, user)
    db.session.add(AuditLog(
        farm_id=payload.farm_id,
        actor_id=user.id,
        action="CREATE_DRAFT",
        resource_type="INVENTORY_COUNT",
        resource_id=draft["id"],
        detail=json.dumps({"countNo": draft["countNo"], "source": "assistant"}, ensure_ascii=False),
    ))
    db.session.commit()
    return {
        "draft": draft,
        "created": True,
        "requiresConfirmation": True,
        "confirmationToken": create_write_confirmation_token(
            user, draft, "inventory-count-post", "inventoryCountId"
        ),
    }


def internal_inventory_count_detail(count_id, user):
    return {"inventoryCount": inventory_count_detail(count_id, user)}


def internal_inventory_count_update(payload, user):
    updated = update_inventory_count(
        payload.count_id,
        UpdateInventoryCountPayload(
            version=payload.version,
            notes=payload.notes,
            lines=payload.lines,
        ),
        user,
    )
    db.session.add(AuditLog(
        farm_id=updated["farmId"],
        actor_id=user.id,
        action="UPDATE_DRAFT",
        resource_type="INVENTORY_COUNT",
        resource_id=updated["id"],
        detail=json.dumps({"countNo": updated["countNo"], "source": "assistant"}, ensure_ascii=False),
    ))
    db.session.commit()
    return {
        "draft": updated,
        "created": False,
        "requiresConfirmation": True,
        "confirmationToken": create_write_confirmation_token(
            user, updated, "inventory-count-post", "inventoryCountId"
        ),
    }


def internal_inventory_count_confirm(confirmation_token, user):
    challenge = resolve_write_confirmation_token(confirmation_token)
    if challenge.get("action") != "inventory-count-post" or not isinstance(challenge.get("inventoryCountId"), int):
        raise ApiError("确认挑战无效", 401, "AGENT_CONFIRMATION_INVALID")
    if challenge["sub"] != user.id:
        raise ApiError("确认挑战不属于当前用户", 403, "AGENT_CONFIRMATION_OWNER_REQUIRED")
    current_version = user.updated_at.isoformat() if user.updated_at else None
    if challenge.get("userVersion") != current_version:
        raise ApiError("确认挑战已失效，请重新生成盘点确认", 401, "AGENT_CONFIRMATION_REVOKED")
    count = db.session.scalar(
        select(InventoryCount).where(InventoryCount.id == challenge["inventoryCountId"]).with_for_update()
    )
    if count is None:
        raise ApiError("盘点单不存在", 404, "INVENTORY_COUNT_NOT_FOUND")
    if count.farm_id != challenge["farmId"]:
        raise ApiError("确认挑战与盘点单不匹配", 409, "AGENT_CONFIRMATION_MISMATCH")
    _farm, farm_role = get_accessible_farm(count.farm_id, user)
    if user.role != "admin" and farm_role != "manager":
        raise ApiError("仅管理员或农场负责人可以确认盘点过账", 403, "AGENT_CONFIRMATION_FORBIDDEN")
    if count.status == "POSTED":
        db.session.add(AuditLog(
            farm_id=count.farm_id,
            actor_id=user.id,
            action="CONFIRM_REPLAY",
            resource_type="INVENTORY_COUNT",
            resource_id=count.id,
            detail=json.dumps({"countNo": count.count_no, "source": "assistant", "action": "inventory-count-post", "replay": True}, ensure_ascii=False),
        ))
        db.session.commit()
        return {"inventoryCount": inventory_count_detail(count.id, user), "confirmed": False, "alreadyPosted": True}
    if count.status != "DRAFT":
        raise ApiError("盘点草稿当前状态不能确认", 409, "INVENTORY_COUNT_NOT_CONFIRMABLE")
    if count.version != challenge["version"]:
        raise ApiError("盘点草稿已被更新，请重新生成确认挑战", 409, "INVENTORY_COUNT_VERSION_CONFLICT")
    _consume_confirmation_nonce(challenge, user, "inventory-count-post", count.id)
    inventory_count = post_inventory_count(
        count.id,
        InventoryCountActionPayload(version=challenge["version"]),
        user,
    )
    db.session.add(AuditLog(
        farm_id=count.farm_id,
        actor_id=user.id,
        action="CONFIRM_WRITE",
        resource_type="INVENTORY_COUNT",
        resource_id=count.id,
        detail=json.dumps({"countNo": count.count_no, "source": "assistant", "action": "inventory-count-post"}, ensure_ascii=False),
    ))
    db.session.commit()
    return {"inventoryCount": inventory_count, "confirmed": True, "alreadyPosted": False}


def internal_stock_transfer_draft(payload, user):
    """创建只保存流水、不改变余额的调拨草稿。"""
    _require_write_access(payload.farm_id, user)
    existing = db.session.scalar(select(StockDocument).where(
        StockDocument.farm_id == payload.farm_id,
        StockDocument.document_no == payload.document_no,
    ))
    if existing is not None:
        if existing.document_type != "WAREHOUSE_TRANSFER" or existing.status != "DRAFT":
            raise ApiError("该库存单号已存在", 409, "TRANSFER_NO_EXISTS", "documentNo")
        transfer = _stock_transfer_payload(existing)
        if not _matching_transfer_payload(transfer, payload):
            raise ApiError("调拨单号已存在且内容不同", 409, "TRANSFER_NO_EXISTS", "documentNo")
        return _transfer_draft_result(transfer, user, False)
    if payload.transfer_date > datetime.now().date():
        raise ApiError("调拨日期不能晚于今天", 400, "TRANSFER_DATE_IN_FUTURE", "transferDate")
    source = _active_warehouse(payload.farm_id, payload.from_warehouse_id)
    destination = _active_warehouse(payload.farm_id, payload.to_warehouse_id)
    item = _active_stock_item(payload.farm_id, payload.item_id, "调拨")
    if item.lot_tracking and not payload.lot_no:
        raise ApiError(f"物料“{item.name}”必须填写批号", 400, "LOT_NO_REQUIRED", "lotNo")
    balance = db.session.scalar(select(InventoryBalance).where(
        InventoryBalance.warehouse_id == source.id,
        InventoryBalance.item_id == item.id,
    ).with_for_update())
    quantity = Decimal(balance.quantity or 0) if balance else Decimal("0")
    if quantity < payload.quantity:
        raise ApiError("调出仓库库存不足", 409, "STOCK_INSUFFICIENT", "quantity", {"available": _number_text(quantity)})
    expires_on = None
    if payload.lot_no:
        lot_quantity, expires_on = _lot_stock(source.id, item.id, payload.lot_no)
        if lot_quantity < payload.quantity:
            raise ApiError("指定批号库存不足", 409, "LOT_STOCK_INSUFFICIENT", "quantity", {"available": _number_text(lot_quantity)})
    document = StockDocument(
        farm_id=payload.farm_id, document_no=payload.document_no, document_type="WAREHOUSE_TRANSFER",
        from_warehouse_id=source.id, to_warehouse_id=destination.id, status="DRAFT",
        source_type="ASSISTANT_TRANSFER", occurred_at=datetime.combine(payload.transfer_date, datetime.min.time()),
        created_by_id=user.id,
    )
    db.session.add(document)
    db.session.flush()
    for warehouse_id, delta in ((source.id, -payload.quantity), (destination.id, payload.quantity)):
        db.session.add(StockMovementLine(
            stock_document_id=document.id, warehouse_id=warehouse_id, item_id=item.id,
            quantity_delta=delta, unit_cost=Decimal(balance.average_cost or 0) if balance else Decimal("0"),
            lot_no=payload.lot_no, expires_on=expires_on,
        ))
    db.session.add(AuditLog(
        farm_id=payload.farm_id, actor_id=user.id, action="CREATE_DRAFT", resource_type="STOCK_DOCUMENT",
        resource_id=document.id, detail=json.dumps({"documentNo": payload.document_no, "source": "assistant"}, ensure_ascii=False),
    ))
    db.session.commit()
    return _transfer_draft_result(_stock_transfer_payload(document), user, True)


def _matching_transfer_payload(transfer, payload):
    return (
        transfer["fromWarehouseId"] == payload.from_warehouse_id
        and transfer["toWarehouseId"] == payload.to_warehouse_id
        and transfer["transferDate"] == payload.transfer_date.isoformat()
        and transfer["itemId"] == payload.item_id
        and Decimal(transfer["quantity"]) == payload.quantity
        and transfer["lotNo"] == payload.lot_no
    )


def _transfer_draft_result(draft, user, created):
    return {
        "draft": draft,
        "created": created,
        "requiresConfirmation": True,
        "confirmationToken": create_write_confirmation_token(user, draft, "stock-transfer-post", "stockTransferId"),
    }


def internal_stock_transfer_confirm(confirmation_token, user):
    challenge = resolve_write_confirmation_token(confirmation_token)
    if challenge.get("action") != "stock-transfer-post" or not isinstance(challenge.get("stockTransferId"), int):
        raise ApiError("确认挑战无效", 401, "AGENT_CONFIRMATION_INVALID")
    if challenge["sub"] != user.id:
        raise ApiError("确认挑战不属于当前用户", 403, "AGENT_CONFIRMATION_OWNER_REQUIRED")
    current_version = user.updated_at.isoformat() if user.updated_at else None
    if challenge.get("userVersion") != current_version:
        raise ApiError("确认挑战已失效，请重新生成调拨确认", 401, "AGENT_CONFIRMATION_REVOKED")
    document = db.session.scalar(select(StockDocument).where(
        StockDocument.id == challenge["stockTransferId"]
    ).with_for_update())
    if document is None or document.farm_id != challenge["farmId"]:
        raise ApiError("调拨单不存在或确认挑战不匹配", 404, "TRANSFER_NOT_FOUND")
    _farm, farm_role = get_accessible_farm(document.farm_id, user)
    if user.role != "admin" and farm_role != "manager":
        raise ApiError("仅管理员或农场负责人可以确认调拨过账", 403, "AGENT_CONFIRMATION_FORBIDDEN")
    if document.status == "POSTED":
        return {"stockTransfer": _stock_transfer_payload(document), "confirmed": False, "alreadyPosted": True}
    if document.status != "DRAFT" or document.version != challenge["version"]:
        raise ApiError("调拨草稿已变化，请重新生成确认挑战", 409, "TRANSFER_VERSION_CONFLICT")
    source_line, destination_line = db.session.scalars(
        select(StockMovementLine).where(StockMovementLine.stock_document_id == document.id).order_by(StockMovementLine.quantity_delta)
    ).all()[:2]
    item_id = source_line.item_id
    warehouse_ids = sorted((document.from_warehouse_id, document.to_warehouse_id))
    balances = db.session.scalars(select(InventoryBalance).where(
        InventoryBalance.item_id == item_id, InventoryBalance.warehouse_id.in_(warehouse_ids)
    ).order_by(InventoryBalance.warehouse_id).with_for_update()).all()
    by_id = {row.warehouse_id: row for row in balances}
    source_balance = by_id.get(document.from_warehouse_id)
    quantity = abs(Decimal(source_line.quantity_delta))
    if source_balance is None or Decimal(source_balance.quantity or 0) < quantity:
        raise ApiError("调出仓库库存不足，请刷新后重试", 409, "STOCK_INSUFFICIENT")
    destination_balance = by_id.get(document.to_warehouse_id)
    if destination_balance is None:
        destination_balance = InventoryBalance(farm_id=document.farm_id, warehouse_id=document.to_warehouse_id, item_id=item_id)
        db.session.add(destination_balance)
    source_cost = Decimal(source_balance.average_cost or 0)
    destination_quantity = Decimal(destination_balance.quantity or 0)
    destination_cost = Decimal(destination_balance.average_cost or 0)
    destination_balance.quantity = destination_quantity + quantity
    destination_balance.average_cost = (((destination_quantity * destination_cost) + (quantity * source_cost)) / destination_balance.quantity).quantize(Decimal("0.0001"))
    source_balance.quantity = Decimal(source_balance.quantity or 0) - quantity
    _consume_confirmation_nonce(challenge, user, "stock-transfer-post", document.id)
    document.status = "POSTED"
    document.version += 1
    db.session.add(AuditLog(
        farm_id=document.farm_id, actor_id=user.id, action="CONFIRM_WRITE", resource_type="STOCK_DOCUMENT",
        resource_id=document.id, detail=json.dumps({"documentNo": document.document_no, "source": "assistant", "action": "stock-transfer-post"}, ensure_ascii=False),
    ))
    db.session.commit()
    return {"stockTransfer": _stock_transfer_payload(document), "confirmed": True, "alreadyPosted": False}


def internal_inventory_summary(farm_id, user):
    return inventory_summary(farm_id, actor=user)


def internal_livestock_summary(farm_id, user):
    return livestock_summary(farm_id, actor=user)
