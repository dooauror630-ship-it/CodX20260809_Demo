from math import ceil

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from ...core.errors import ApiError
from ...extensions import db
from ..auth.service import format_datetime
from ..catalog.models import Unit
from ..farm.models import Farm
from ..farm.service import get_accessible_farm
from .models import Item, ItemCategory, Warehouse


def _paginated(items, query, total):
    return {
        "items": items,
        "pagination": {
            "page": query.page,
            "pageSize": query.page_size,
            "total": total,
            "totalPages": ceil(total / query.page_size) if total else 0,
        },
    }


def _active_farm(farm_id):
    farm = db.session.get(Farm, farm_id)
    if farm is None:
        raise ApiError("农场不存在", 404, "FARM_NOT_FOUND")
    if not farm.is_active:
        raise ApiError("农场已停用，不能新增基础资料", 409, "FARM_DISABLED")
    return farm


def _status_conditions(model, status):
    if status == "active":
        return [model.is_active.is_(True)]
    if status == "disabled":
        return [model.is_active.is_(False)]
    return []


def warehouse_payload(warehouse):
    return {
        "id": warehouse.id,
        "farmId": warehouse.farm_id,
        "code": warehouse.code,
        "name": warehouse.name,
        "location": warehouse.location,
        "isActive": warehouse.is_active,
        "createdAt": format_datetime(warehouse.created_at),
        "updatedAt": format_datetime(warehouse.updated_at),
    }


def list_warehouses(query, actor):
    get_accessible_farm(query.farm_id, actor)
    conditions = [Warehouse.farm_id == query.farm_id, *_status_conditions(Warehouse, query.status)]
    if query.keyword:
        conditions.append(or_(
            Warehouse.code.contains(query.keyword, autoescape=True),
            Warehouse.name.contains(query.keyword, autoescape=True),
            Warehouse.location.contains(query.keyword, autoescape=True),
        ))
    total = db.session.scalar(select(func.count(Warehouse.id)).where(*conditions)) or 0
    warehouses = db.session.scalars(
        select(Warehouse)
        .where(*conditions)
        .order_by(Warehouse.is_active.desc(), Warehouse.name, Warehouse.id)
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
    ).all()
    return _paginated([warehouse_payload(item) for item in warehouses], query, total)


def create_warehouse(payload, actor):
    _active_farm(payload.farm_id)
    warehouse = Warehouse(
        farm_id=payload.farm_id,
        code=payload.code,
        name=payload.name,
        location=payload.location,
        created_by_id=actor.id,
        updated_by_id=actor.id,
    )
    db.session.add(warehouse)
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ApiError("该农场内仓库编号已存在", 409, "WAREHOUSE_CODE_EXISTS", "code") from error
    return warehouse_payload(warehouse)


def update_warehouse(warehouse_id, payload, actor):
    warehouse = db.session.get(Warehouse, warehouse_id)
    if warehouse is None:
        raise ApiError("仓库不存在", 404, "WAREHOUSE_NOT_FOUND")
    for field in ("code", "name", "location", "is_active"):
        if field in payload.model_fields_set:
            setattr(warehouse, field, getattr(payload, field))
    warehouse.updated_by_id = actor.id
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ApiError("该农场内仓库编号已存在", 409, "WAREHOUSE_CODE_EXISTS", "code") from error
    return warehouse_payload(warehouse)


def category_payload(category, parent_name=None):
    return {
        "id": category.id,
        "farmId": category.farm_id,
        "parentId": category.parent_id,
        "parentName": parent_name,
        "code": category.code,
        "name": category.name,
        "isActive": category.is_active,
        "createdAt": format_datetime(category.created_at),
        "updatedAt": format_datetime(category.updated_at),
    }


def list_categories(query, actor):
    get_accessible_farm(query.farm_id, actor)
    conditions = [ItemCategory.farm_id == query.farm_id, *_status_conditions(ItemCategory, query.status)]
    if query.keyword:
        conditions.append(or_(
            ItemCategory.code.contains(query.keyword, autoescape=True),
            ItemCategory.name.contains(query.keyword, autoescape=True),
        ))
    categories = db.session.scalars(
        select(ItemCategory)
        .where(*conditions)
        .order_by(ItemCategory.parent_id.is_not(None), ItemCategory.parent_id, ItemCategory.name, ItemCategory.id)
    ).all()
    names = dict(db.session.execute(
        select(ItemCategory.id, ItemCategory.name).where(ItemCategory.farm_id == query.farm_id)
    ).all())
    return {"items": [category_payload(item, names.get(item.parent_id)) for item in categories]}


def _category_parent(farm_id, parent_id, category_id=None):
    if parent_id is None:
        return None
    parent = db.session.get(ItemCategory, parent_id)
    if parent is None:
        raise ApiError("上级分类不存在", 404, "CATEGORY_PARENT_NOT_FOUND")
    if parent.farm_id != farm_id:
        raise ApiError("不能引用其他农场的分类", 409, "CATEGORY_FARM_MISMATCH")
    if not parent.is_active:
        raise ApiError("上级分类已停用", 409, "CATEGORY_PARENT_DISABLED")
    if parent.id == category_id or parent.parent_id is not None:
        raise ApiError("物料分类最多支持两层", 409, "CATEGORY_DEPTH_EXCEEDED")
    if category_id is not None:
        has_children = db.session.scalar(
            select(func.count(ItemCategory.id)).where(ItemCategory.parent_id == category_id)
        )
        if has_children:
            raise ApiError("包含下级分类的分类不能再设置上级", 409, "CATEGORY_DEPTH_EXCEEDED")
    return parent


def create_category(payload, actor):
    _active_farm(payload.farm_id)
    parent = _category_parent(payload.farm_id, payload.parent_id)
    category = ItemCategory(
        farm_id=payload.farm_id,
        parent_id=parent.id if parent else None,
        code=payload.code,
        name=payload.name,
        created_by_id=actor.id,
        updated_by_id=actor.id,
    )
    db.session.add(category)
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ApiError("该农场内物料分类编号已存在", 409, "CATEGORY_CODE_EXISTS", "code") from error
    return category_payload(category, parent.name if parent else None)


def update_category(category_id, payload, actor):
    category = db.session.get(ItemCategory, category_id)
    if category is None:
        raise ApiError("物料分类不存在", 404, "CATEGORY_NOT_FOUND")
    parent = None
    if "parent_id" in payload.model_fields_set:
        parent = _category_parent(category.farm_id, payload.parent_id, category.id)
    for field in ("parent_id", "code", "name", "is_active"):
        if field in payload.model_fields_set:
            setattr(category, field, getattr(payload, field))
    category.updated_by_id = actor.id
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ApiError("该农场内物料分类编号已存在", 409, "CATEGORY_CODE_EXISTS", "code") from error
    parent_name = parent.name if parent else (
        db.session.get(ItemCategory, category.parent_id).name if category.parent_id else None
    )
    return category_payload(category, parent_name)


def _active_category(farm_id, category_id):
    category = db.session.get(ItemCategory, category_id)
    if category is None:
        raise ApiError("物料分类不存在", 404, "CATEGORY_NOT_FOUND")
    if category.farm_id != farm_id:
        raise ApiError("不能引用其他农场的分类", 409, "CATEGORY_FARM_MISMATCH")
    if not category.is_active:
        raise ApiError("物料分类已停用", 409, "CATEGORY_DISABLED")
    if category.parent_id:
        parent = db.session.get(ItemCategory, category.parent_id)
        if parent is None or not parent.is_active:
            raise ApiError("上级物料分类已停用", 409, "CATEGORY_PARENT_DISABLED")
    return category


def _active_unit(unit_id):
    unit = db.session.get(Unit, unit_id)
    if unit is None:
        raise ApiError("计量单位不存在", 404, "UNIT_NOT_FOUND")
    if not unit.is_active:
        raise ApiError("计量单位已停用", 409, "UNIT_DISABLED")
    return unit


def _number_text(value):
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def item_payload(item, category, unit):
    return {
        "id": item.id,
        "farmId": item.farm_id,
        "categoryId": item.category_id,
        "categoryName": category.name,
        "unitId": item.unit_id,
        "unitName": unit.name,
        "unitCode": unit.code,
        "code": item.code,
        "name": item.name,
        "itemType": item.item_type,
        "safetyStock": _number_text(item.safety_stock),
        "lotTracking": item.lot_tracking,
        "isActive": item.is_active,
        "createdAt": format_datetime(item.created_at),
        "updatedAt": format_datetime(item.updated_at),
    }


def list_items(query, actor):
    get_accessible_farm(query.farm_id, actor)
    conditions = [Item.farm_id == query.farm_id, *_status_conditions(Item, query.status)]
    if query.keyword:
        conditions.append(or_(
            Item.code.contains(query.keyword, autoescape=True),
            Item.name.contains(query.keyword, autoescape=True),
        ))
    if query.category_id:
        conditions.append(Item.category_id == query.category_id)
    total = db.session.scalar(select(func.count(Item.id)).where(*conditions)) or 0
    rows = db.session.execute(
        select(Item, ItemCategory, Unit)
        .join(ItemCategory, ItemCategory.id == Item.category_id)
        .join(Unit, Unit.id == Item.unit_id)
        .where(*conditions)
        .order_by(Item.is_active.desc(), Item.name, Item.id)
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
    ).all()
    return _paginated([item_payload(*row) for row in rows], query, total)


def create_item(payload, actor):
    _active_farm(payload.farm_id)
    category = _active_category(payload.farm_id, payload.category_id)
    unit = _active_unit(payload.unit_id)
    item = Item(
        farm_id=payload.farm_id,
        category_id=payload.category_id,
        unit_id=payload.unit_id,
        code=payload.code,
        name=payload.name,
        item_type=payload.item_type,
        safety_stock=payload.safety_stock,
        lot_tracking=payload.lot_tracking,
        created_by_id=actor.id,
        updated_by_id=actor.id,
    )
    db.session.add(item)
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ApiError("该农场内物料编号已存在", 409, "ITEM_CODE_EXISTS", "code") from error
    return item_payload(item, category, unit)


def update_item(item_id, payload, actor):
    item = db.session.get(Item, item_id)
    if item is None:
        raise ApiError("物料不存在", 404, "ITEM_NOT_FOUND")
    category_id = payload.category_id if "category_id" in payload.model_fields_set else item.category_id
    unit_id = payload.unit_id if "unit_id" in payload.model_fields_set else item.unit_id
    category = _active_category(item.farm_id, category_id)
    unit = _active_unit(unit_id)
    for field in (
        "category_id", "unit_id", "code", "name", "item_type",
        "safety_stock", "lot_tracking", "is_active",
    ):
        if field in payload.model_fields_set:
            setattr(item, field, getattr(payload, field))
    item.updated_by_id = actor.id
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ApiError("该农场内物料编号已存在", 409, "ITEM_CODE_EXISTS", "code") from error
    return item_payload(item, category, unit)
