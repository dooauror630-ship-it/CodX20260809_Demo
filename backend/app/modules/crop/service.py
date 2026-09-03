from datetime import date
from datetime import datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
from math import ceil

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from ...core.errors import ApiError
from ...extensions import db
from ..auth.service import format_datetime
from ..catalog.models import CropType, CropVariety
from ..farm.models import Plot
from ..farm.service import get_accessible_farm
from ..catalog.models import Unit
from ..inventory.models import Item, StockDocument, StockMovementLine
from ..inventory.purchase_service import _require_write_access
from .models import CropCycle, FieldOperation, FieldOperationInput, HarvestBatch, TobaccoCuringBatch
from ..inventory.models import Warehouse


OPEN_STATUSES = ("PLANNED", "ACTIVE", "HARVESTING")
TRANSITIONS = {
    "PLANNED": {"ACTIVE", "CANCELLED"},
    "ACTIVE": {"HARVESTING", "CLOSED", "CANCELLED"},
    "HARVESTING": {"CLOSED", "CANCELLED"},
    "CLOSED": set(),
    "CANCELLED": set(),
}


def _decimal_text(value):
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def crop_cycle_payload(cycle, plot=None, crop_type=None, variety=None):
    return {
        "id": cycle.id,
        "farmId": cycle.farm_id,
        "cycleCode": cycle.cycle_code,
        "plotId": cycle.plot_id,
        "plotName": plot.name if plot else None,
        "cropTypeId": cycle.crop_type_id,
        "cropTypeName": crop_type.name if crop_type else None,
        "varietyId": cycle.variety_id,
        "varietyName": variety.name if variety else None,
        "areaMu": _decimal_text(cycle.area_mu),
        "plannedStartDate": cycle.planned_start_date.isoformat(),
        "plannedEndDate": cycle.planned_end_date.isoformat(),
        "actualStartDate": cycle.actual_start_date.isoformat() if cycle.actual_start_date else None,
        "actualEndDate": cycle.actual_end_date.isoformat() if cycle.actual_end_date else None,
        "status": cycle.status,
        "notes": cycle.notes,
        "createdById": cycle.created_by_id,
        "updatedById": cycle.updated_by_id,
        "createdAt": format_datetime(cycle.created_at),
        "updatedAt": format_datetime(cycle.updated_at),
    }


def _load_references(payload):
    plot = db.session.get(Plot, payload.plot_id)
    if plot is None:
        raise ApiError("地块不存在", 404, "PLOT_NOT_FOUND", "plotId")
    if plot.farm_id != payload.farm_id:
        raise ApiError("地块不属于当前农场", 409, "PLOT_FARM_MISMATCH", "plotId")
    if not plot.is_active:
        raise ApiError("地块已停用", 409, "PLOT_DISABLED", "plotId")
    crop_type = db.session.get(CropType, payload.crop_type_id)
    if crop_type is None:
        raise ApiError("作物类型不存在", 404, "CROP_TYPE_NOT_FOUND", "cropTypeId")
    if not crop_type.is_active:
        raise ApiError("作物类型已停用", 409, "CROP_TYPE_DISABLED", "cropTypeId")
    variety = db.session.get(CropVariety, payload.variety_id)
    if variety is None:
        raise ApiError("作物品种不存在", 404, "CROP_VARIETY_NOT_FOUND", "varietyId")
    if variety.crop_type_id != crop_type.id:
        raise ApiError("品种不属于当前作物类型", 409, "CROP_VARIETY_TYPE_MISMATCH", "varietyId")
    if not variety.is_active:
        raise ApiError("作物品种已停用", 409, "CROP_VARIETY_DISABLED", "varietyId")
    if payload.area_mu > plot.area_mu:
        raise ApiError("种植面积不能超过地块面积", 409, "CROP_CYCLE_AREA_EXCEEDED", "areaMu", {
            "plotAreaMu": _decimal_text(plot.area_mu),
        })
    return plot, crop_type, variety


def _ensure_area_available(plot_id, start_date, end_date, area_mu, exclude_id=None):
    conditions = [
        CropCycle.plot_id == plot_id,
        CropCycle.status.in_(OPEN_STATUSES),
        CropCycle.planned_start_date <= end_date,
        CropCycle.planned_end_date >= start_date,
    ]
    if exclude_id is not None:
        conditions.append(CropCycle.id != exclude_id)
    used = db.session.scalar(select(func.coalesce(func.sum(CropCycle.area_mu), 0)).where(*conditions)) or 0
    if used + area_mu > db.session.get(Plot, plot_id).area_mu:
        raise ApiError(
            "同一地块重叠周期的种植面积超过地块可用面积",
            409,
            "CROP_CYCLE_OVERLAP_AREA_EXCEEDED",
            "areaMu",
            {"usedAreaMu": _decimal_text(used), "requestedAreaMu": _decimal_text(area_mu)},
        )


def list_crop_cycles(query, actor):
    get_accessible_farm(query.farm_id, actor)
    conditions = [CropCycle.farm_id == query.farm_id]
    if query.status != "all":
        conditions.append(CropCycle.status == query.status)
    if query.keyword:
        conditions.append(or_(
            CropCycle.cycle_code.contains(query.keyword, autoescape=True),
            Plot.name.contains(query.keyword, autoescape=True),
            CropType.name.contains(query.keyword, autoescape=True),
            CropVariety.name.contains(query.keyword, autoescape=True),
        ))
    statement = (
        select(CropCycle, Plot, CropType, CropVariety)
        .join(Plot, Plot.id == CropCycle.plot_id)
        .join(CropType, CropType.id == CropCycle.crop_type_id)
        .join(CropVariety, CropVariety.id == CropCycle.variety_id)
        .where(*conditions)
    )
    total = db.session.scalar(select(func.count(CropCycle.id)).select_from(CropCycle).join(Plot).join(CropType).join(CropVariety).where(*conditions)) or 0
    rows = db.session.execute(
        statement.order_by(CropCycle.planned_start_date.desc(), CropCycle.id.desc())
        .offset((query.page - 1) * query.page_size).limit(query.page_size)
    ).all()
    return {
        "items": [crop_cycle_payload(*row) for row in rows],
        "pagination": {
            "page": query.page, "pageSize": query.page_size, "total": total,
            "totalPages": ceil(total / query.page_size) if total else 0,
        },
    }


def get_crop_cycle(cycle_id, actor):
    row = db.session.execute(
        select(CropCycle, Plot, CropType, CropVariety)
        .join(Plot, Plot.id == CropCycle.plot_id)
        .join(CropType, CropType.id == CropCycle.crop_type_id)
        .join(CropVariety, CropVariety.id == CropCycle.variety_id)
        .where(CropCycle.id == cycle_id)
    ).first()
    if row is None:
        raise ApiError("种植周期不存在", 404, "CROP_CYCLE_NOT_FOUND")
    get_accessible_farm(row[0].farm_id, actor)
    return crop_cycle_payload(*row)


def crop_cycle_cost_summary(cycle_id, actor):
    cycle = db.session.get(CropCycle, cycle_id)
    if cycle is None:
        raise ApiError("种植周期不存在", 404, "CROP_CYCLE_NOT_FOUND")
    get_accessible_farm(cycle.farm_id, actor)
    material_cost, document_count = db.session.execute(
        select(
            func.coalesce(func.sum(StockMovementLine.quantity_delta * StockMovementLine.unit_cost * -1), 0),
            func.count(func.distinct(StockDocument.id)),
        )
        .select_from(StockMovementLine)
        .join(StockDocument, StockDocument.id == StockMovementLine.stock_document_id)
        .where(
            StockDocument.farm_id == cycle.farm_id,
            StockDocument.status == "POSTED",
            StockDocument.document_type.in_(("PRODUCTION_ISSUE", "PRODUCTION_RETURN")),
            StockMovementLine.cost_object_type == "CROP_CYCLE",
            StockMovementLine.cost_object_id == cycle.id,
        )
    ).one()
    labor_cost, service_cost, operation_count = db.session.execute(
        select(
            func.coalesce(func.sum(FieldOperation.labor_cost), 0),
            func.coalesce(func.sum(FieldOperation.service_cost), 0),
            func.count(FieldOperation.id),
        ).where(FieldOperation.crop_cycle_id == cycle.id)
    ).one()
    curing_cost = db.session.scalar(
        select(func.coalesce(func.sum(TobaccoCuringBatch.fuel_cost + TobaccoCuringBatch.electricity_cost), 0))
        .where(TobaccoCuringBatch.crop_cycle_id == cycle.id)
    ) or 0
    material_cost = Decimal(material_cost or 0)
    labor_cost = Decimal(labor_cost or 0)
    service_cost = Decimal(service_cost or 0)
    curing_cost = Decimal(curing_cost)
    total_cost = material_cost + labor_cost + service_cost + curing_cost
    cost_per_mu = total_cost / cycle.area_mu if cycle.area_mu else Decimal("0")
    return {
        "cropCycleId": cycle.id,
        "materialCost": format(material_cost, ".2f"),
        "laborCost": format(labor_cost, ".2f"),
        "serviceCost": format(service_cost, ".2f"),
        "curingCost": format(curing_cost, ".2f"),
        "totalCost": format(total_cost, ".2f"),
        "costPerMu": format(cost_per_mu, ".2f"),
        "inputDocumentCount": document_count,
        "operationCount": operation_count,
    }


def create_crop_cycle(payload, actor):
    _require_write_access(payload.farm_id, actor)
    existing = db.session.scalar(select(CropCycle).where(
        CropCycle.farm_id == payload.farm_id, CropCycle.cycle_code == payload.cycle_code,
    ))
    if existing is not None:
        matches = all((
            existing.plot_id == payload.plot_id, existing.crop_type_id == payload.crop_type_id,
            existing.variety_id == payload.variety_id, existing.area_mu == payload.area_mu,
            existing.planned_start_date == payload.planned_start_date,
            existing.planned_end_date == payload.planned_end_date, existing.notes == payload.notes,
        ))
        if not matches:
            raise ApiError("种植周期编号已存在且内容不同", 409, "CROP_CYCLE_CODE_EXISTS", "cycleCode")
        return get_crop_cycle(existing.id, actor), False
    plot, _crop_type, _variety = _load_references(payload)
    _ensure_area_available(plot.id, payload.planned_start_date, payload.planned_end_date, payload.area_mu)
    cycle = CropCycle(
        farm_id=payload.farm_id, cycle_code=payload.cycle_code, plot_id=plot.id,
        crop_type_id=payload.crop_type_id, variety_id=payload.variety_id, area_mu=payload.area_mu,
        planned_start_date=payload.planned_start_date, planned_end_date=payload.planned_end_date,
        notes=payload.notes, created_by_id=actor.id, updated_by_id=actor.id,
    )
    db.session.add(cycle)
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ApiError("种植周期登记冲突，请刷新后重试", 409, "CROP_CYCLE_CONFLICT") from error
    return get_crop_cycle(cycle.id, actor), True


def update_crop_cycle_status(cycle_id, payload, actor):
    cycle = db.session.scalar(select(CropCycle).where(CropCycle.id == cycle_id).with_for_update())
    if cycle is None:
        raise ApiError("种植周期不存在", 404, "CROP_CYCLE_NOT_FOUND")
    _require_write_access(cycle.farm_id, actor)
    if payload.status not in TRANSITIONS[cycle.status] and payload.status != cycle.status:
        raise ApiError("种植周期状态不能从当前状态变更", 409, "CROP_CYCLE_STATUS_INVALID", "status")
    actual_start = payload.actual_start_date
    actual_end = payload.actual_end_date
    if payload.status == "PLANNED":
        actual_start = actual_end = None
    elif payload.status in ("ACTIVE", "HARVESTING"):
        actual_start = actual_start or cycle.actual_start_date or date.today()
        actual_end = None
    elif payload.status == "CLOSED":
        actual_start = actual_start or cycle.actual_start_date or date.today()
        actual_end = actual_end or date.today()
    elif payload.status == "CANCELLED":
        actual_end = None
    if actual_start and actual_start > date.today() or actual_end and actual_end > date.today():
        raise ApiError("实际日期不能晚于今天", 400, "CROP_CYCLE_ACTUAL_DATE_IN_FUTURE")
    if actual_start and actual_start < cycle.planned_start_date:
        raise ApiError("实际开始日期不能早于计划开始日期", 409, "CROP_CYCLE_ACTUAL_START_INVALID", "actualStartDate")
    if actual_end and actual_start and actual_end < actual_start:
        raise ApiError("实际结束日期不能早于实际开始日期", 409, "CROP_CYCLE_ACTUAL_END_INVALID", "actualEndDate")
    if payload.status in ("ACTIVE", "HARVESTING"):
        _ensure_area_available(cycle.plot_id, cycle.planned_start_date, cycle.planned_end_date, cycle.area_mu, cycle.id)
    cycle.status = payload.status
    cycle.actual_start_date = actual_start
    cycle.actual_end_date = actual_end
    cycle.updated_by_id = actor.id
    db.session.commit()
    return get_crop_cycle(cycle.id, actor)


def field_operation_payload(operation):
    def number_text(value, places=2):
        return format(value, f".{places}f")

    return {
        "id": operation.id,
        "farmId": operation.farm_id,
        "cropCycleId": operation.crop_cycle_id,
        "operationType": operation.operation_type,
        "operationDate": operation.operation_date.isoformat(),
        "areaMu": _decimal_text(operation.area_mu),
        "laborHours": number_text(operation.labor_hours),
        "machineHours": number_text(operation.machine_hours),
        "laborCost": number_text(operation.labor_cost),
        "serviceCost": number_text(operation.service_cost),
        "notes": operation.notes,
        "createdById": operation.created_by_id,
        "createdAt": format_datetime(operation.created_at),
    }


def _get_operation_cycle(payload):
    cycle = db.session.get(CropCycle, payload.crop_cycle_id)
    if cycle is None:
        raise ApiError("种植周期不存在", 404, "CROP_CYCLE_NOT_FOUND", "cropCycleId")
    if cycle.farm_id != payload.farm_id:
        raise ApiError("种植周期不属于当前农场", 409, "CROP_CYCLE_FARM_MISMATCH", "cropCycleId")
    if cycle.status not in ("ACTIVE", "HARVESTING"):
        raise ApiError("当前周期状态不能登记农事操作", 409, "CROP_CYCLE_OPERATION_STATUS_INVALID")
    return cycle


def list_field_operations(query, actor):
    get_accessible_farm(query.farm_id, actor)
    cycle = db.session.get(CropCycle, query.crop_cycle_id)
    if cycle is None:
        raise ApiError("种植周期不存在", 404, "CROP_CYCLE_NOT_FOUND", "cropCycleId")
    if cycle.farm_id != query.farm_id:
        raise ApiError("种植周期不属于当前农场", 409, "CROP_CYCLE_FARM_MISMATCH", "cropCycleId")
    conditions = [
        FieldOperation.farm_id == query.farm_id,
        FieldOperation.crop_cycle_id == query.crop_cycle_id,
    ]
    total = db.session.scalar(select(func.count(FieldOperation.id)).where(*conditions)) or 0
    operations = db.session.scalars(
        select(FieldOperation).where(*conditions)
        .order_by(FieldOperation.operation_date.desc(), FieldOperation.id.desc())
        .offset((query.page - 1) * query.page_size).limit(query.page_size)
    ).all()
    return {
        "items": [field_operation_payload(operation) for operation in operations],
        "pagination": {
            "page": query.page, "pageSize": query.page_size, "total": total,
            "totalPages": ceil(total / query.page_size) if total else 0,
        },
    }


def create_field_operation(payload, actor):
    _require_write_access(payload.farm_id, actor)
    cycle = _get_operation_cycle(payload)
    if payload.operation_date > date.today():
        raise ApiError("农事日期不能晚于今天", 400, "FIELD_OPERATION_IN_FUTURE", "operationDate")
    lower_bound = cycle.actual_start_date or cycle.planned_start_date
    if payload.operation_date < lower_bound:
        raise ApiError("农事日期不能早于周期开始日期", 409, "FIELD_OPERATION_BEFORE_START", "operationDate")
    if cycle.actual_end_date and payload.operation_date > cycle.actual_end_date:
        raise ApiError("农事日期不能晚于周期结束日期", 409, "FIELD_OPERATION_AFTER_END", "operationDate")
    if payload.area_mu > cycle.area_mu:
        raise ApiError("农事作业面积不能超过周期占用面积", 409, "FIELD_OPERATION_AREA_EXCEEDED", "areaMu", {
            "cycleAreaMu": _decimal_text(cycle.area_mu),
        })
    operation = FieldOperation(
        farm_id=payload.farm_id,
        crop_cycle_id=payload.crop_cycle_id,
        operation_type=payload.operation_type,
        operation_date=payload.operation_date,
        area_mu=payload.area_mu,
        labor_hours=payload.labor_hours,
        machine_hours=payload.machine_hours,
        labor_cost=payload.labor_cost,
        service_cost=payload.service_cost,
        notes=payload.notes,
        created_by_id=actor.id,
    )
    db.session.add(operation)
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ApiError("农事操作登记冲突，请刷新后重试", 409, "FIELD_OPERATION_CONFLICT") from error
    return field_operation_payload(operation)


def _get_field_operation_for_input(farm_id, field_operation_id, actor):
    operation = db.session.get(FieldOperation, field_operation_id)
    if operation is None:
        raise ApiError("农事操作不存在", 404, "FIELD_OPERATION_NOT_FOUND", "fieldOperationId")
    if operation.farm_id != farm_id:
        raise ApiError("农事操作不属于当前农场", 409, "FIELD_OPERATION_FARM_MISMATCH", "fieldOperationId")
    get_accessible_farm(farm_id, actor)
    return operation


def _field_operation_input_payload(record, document, line, item, unit):
    return {
        "id": record.id,
        "farmId": record.farm_id,
        "fieldOperationId": record.field_operation_id,
        "stockDocumentId": record.stock_document_id,
        "documentNo": document.document_no,
        "itemId": record.item_id,
        "itemCode": item.code,
        "itemName": item.name,
        "unitName": unit.name,
        "quantity": _decimal_text(record.quantity),
        "amount": format(record.amount, ".2f"),
        "unitCost": _decimal_text(line.unit_cost),
        "operationDate": document.occurred_at.date().isoformat(),
        "createdById": record.created_by_id,
        "createdAt": format_datetime(record.created_at),
    }


def _field_operation_input_rows(operation):
    conditions = [
        StockDocument.farm_id == operation.farm_id,
        StockDocument.status == "POSTED",
        StockDocument.document_type == "PRODUCTION_ISSUE",
        StockMovementLine.stock_document_id == StockDocument.id,
        StockMovementLine.cost_object_type == "CROP_CYCLE",
        StockMovementLine.cost_object_id == operation.crop_cycle_id,
        StockDocument.occurred_at < datetime.combine(operation.operation_date + timedelta(days=1), time.min),
    ]
    conditions.append(FieldOperationInput.field_operation_id == operation.id)
    return db.session.execute(
        select(FieldOperationInput, StockDocument, StockMovementLine, Item, Unit)
        .select_from(FieldOperationInput)
        .join(StockDocument, StockDocument.id == FieldOperationInput.stock_document_id)
        .join(StockMovementLine, StockMovementLine.stock_document_id == StockDocument.id)
        .where(StockMovementLine.item_id == FieldOperationInput.item_id)
        .join(Item, Item.id == FieldOperationInput.item_id)
        .join(Unit, Unit.id == Item.unit_id)
        .where(*conditions)
        .order_by(StockDocument.occurred_at.desc(), StockDocument.id.desc())
    ).all()


def _available_field_operation_input_rows(operation):
    conditions = [
        StockDocument.farm_id == operation.farm_id,
        StockDocument.status == "POSTED",
        StockDocument.document_type == "PRODUCTION_ISSUE",
        StockDocument.occurred_at < datetime.combine(operation.operation_date + timedelta(days=1), time.min),
        StockMovementLine.stock_document_id == StockDocument.id,
        StockMovementLine.cost_object_type == "CROP_CYCLE",
        StockMovementLine.cost_object_id == operation.crop_cycle_id,
        StockMovementLine.quantity_delta < 0,
        ~select(FieldOperationInput.id)
        .where(FieldOperationInput.stock_document_id == StockDocument.id)
        .exists(),
    ]
    return db.session.execute(
        select(StockDocument, StockMovementLine, Item, Unit)
        .select_from(StockDocument)
        .join(StockMovementLine, StockMovementLine.stock_document_id == StockDocument.id)
        .join(Item, Item.id == StockMovementLine.item_id)
        .join(Unit, Unit.id == Item.unit_id)
        .where(*conditions)
        .order_by(StockDocument.occurred_at.desc(), StockDocument.id.desc())
    ).all()


def list_field_operation_inputs(query, actor):
    operation = _get_field_operation_for_input(query.farm_id, query.field_operation_id, actor)
    rows = _field_operation_input_rows(operation)
    return {
        "items": [_field_operation_input_payload(record, document, line, item, unit) for record, document, line, item, unit in rows],
        "total": len(rows),
    }


def list_available_field_operation_inputs(query, actor):
    operation = _get_field_operation_for_input(query.farm_id, query.field_operation_id, actor)
    rows = _available_field_operation_input_rows(operation)
    return {
        "items": [
            {
                "stockDocumentId": document.id,
                "documentNo": document.document_no,
                "itemId": line.item_id,
                "itemCode": item.code,
                "itemName": item.name,
                "unitName": unit.name,
                "quantity": _decimal_text(abs(line.quantity_delta)),
                "amount": format(
                    (abs(line.quantity_delta) * line.unit_cost).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                    ".2f",
                ),
                "operationDate": document.occurred_at.date().isoformat(),
            }
            for document, line, item, unit in rows
        ],
        "total": len(rows),
    }


def create_field_operation_input(payload, actor):
    _require_write_access(payload.farm_id, actor)
    operation = _get_field_operation_for_input(payload.farm_id, payload.field_operation_id, actor)
    document = db.session.get(StockDocument, payload.stock_document_id)
    if document is None:
        raise ApiError("库存单据不存在", 404, "STOCK_DOCUMENT_NOT_FOUND", "stockDocumentId")
    if document.farm_id != operation.farm_id:
        raise ApiError("库存单据不属于当前农场", 409, "STOCK_DOCUMENT_FARM_MISMATCH", "stockDocumentId")
    cycle = db.session.get(CropCycle, operation.crop_cycle_id)
    if cycle.status not in ("ACTIVE", "HARVESTING"):
        raise ApiError("当前种植周期状态不能绑定投入品", 409, "CROP_CYCLE_INPUT_STATUS_INVALID")
    if document.document_type != "PRODUCTION_ISSUE" or document.status != "POSTED":
        raise ApiError("只能绑定已过账的生产领料单", 409, "FIELD_INPUT_DOCUMENT_INVALID", "stockDocumentId")
    if document.occurred_at.date() > operation.operation_date:
        raise ApiError("投入品领料日期不能晚于农事操作日期", 409, "FIELD_INPUT_DATE_AFTER_OPERATION", "stockDocumentId")
    line = db.session.scalar(
        select(StockMovementLine).where(StockMovementLine.stock_document_id == document.id)
    )
    if line is None or line.quantity_delta >= 0:
        raise ApiError("生产领料单流水不完整", 409, "FIELD_INPUT_DOCUMENT_INVALID", "stockDocumentId")
    if line.cost_object_type != "CROP_CYCLE" or line.cost_object_id != operation.crop_cycle_id:
        raise ApiError("库存领料单成本对象与农事周期不一致", 409, "FIELD_INPUT_COST_OBJECT_MISMATCH", "stockDocumentId")
    existing = db.session.scalar(
        select(FieldOperationInput).where(FieldOperationInput.stock_document_id == document.id)
    )
    if existing is not None:
        if existing.field_operation_id == operation.id:
            row = db.session.execute(
                select(FieldOperationInput, StockDocument, StockMovementLine, Item, Unit)
                .select_from(FieldOperationInput)
                .join(StockDocument, StockDocument.id == FieldOperationInput.stock_document_id)
                .join(StockMovementLine, StockMovementLine.stock_document_id == StockDocument.id)
                .join(Item, Item.id == FieldOperationInput.item_id)
                .join(Unit, Unit.id == Item.unit_id)
                .where(FieldOperationInput.id == existing.id)
            ).one()
            return _field_operation_input_payload(*row), False
        raise ApiError("该库存领料单已绑定其他农事操作", 409, "FIELD_INPUT_DOCUMENT_BOUND", "stockDocumentId")
    record = FieldOperationInput(
        farm_id=operation.farm_id,
        field_operation_id=operation.id,
        stock_document_id=document.id,
        item_id=line.item_id,
        quantity=abs(line.quantity_delta),
        amount=(abs(line.quantity_delta) * line.unit_cost).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        created_by_id=actor.id,
    )
    db.session.add(record)
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        existing = db.session.scalar(select(FieldOperationInput).where(FieldOperationInput.stock_document_id == document.id))
        if existing is not None and existing.field_operation_id == operation.id:
            return create_field_operation_input(payload, actor)
        raise ApiError("农事投入品绑定冲突，请刷新后重试", 409, "FIELD_INPUT_CONFLICT") from error
    row = db.session.execute(
        select(FieldOperationInput, StockDocument, StockMovementLine, Item, Unit)
        .select_from(FieldOperationInput)
        .join(StockDocument, StockDocument.id == record.stock_document_id)
        .join(StockMovementLine, StockMovementLine.stock_document_id == record.stock_document_id)
        .join(Item, Item.id == record.item_id)
        .join(Unit, Unit.id == Item.unit_id)
        .where(FieldOperationInput.id == record.id)
    ).one()
    return _field_operation_input_payload(*row), True


def _harvest_payload(batch, unit, warehouse):
    return {
        "id": batch.id, "farmId": batch.farm_id, "cropCycleId": batch.crop_cycle_id,
        "harvestNo": batch.harvest_no, "harvestDate": batch.harvest_date.isoformat(),
        "grossWeight": _decimal_text(batch.gross_weight), "netWeight": _decimal_text(batch.net_weight),
        "unitId": batch.unit_id, "unitName": unit.name, "warehouseId": batch.warehouse_id,
        "warehouseName": warehouse.name, "notes": batch.notes, "createdById": batch.created_by_id,
        "createdAt": format_datetime(batch.created_at),
    }


def list_harvest_batches(query, actor):
    get_accessible_farm(query.farm_id, actor)
    cycle = db.session.get(CropCycle, query.crop_cycle_id)
    if cycle is None:
        raise ApiError("种植周期不存在", 404, "CROP_CYCLE_NOT_FOUND", "cropCycleId")
    if cycle.farm_id != query.farm_id:
        raise ApiError("种植周期不属于当前农场", 409, "CROP_CYCLE_FARM_MISMATCH", "cropCycleId")
    rows = db.session.execute(
        select(HarvestBatch, Unit, Warehouse)
        .join(Unit, Unit.id == HarvestBatch.unit_id)
        .join(Warehouse, Warehouse.id == HarvestBatch.warehouse_id)
        .where(HarvestBatch.crop_cycle_id == cycle.id)
        .order_by(HarvestBatch.harvest_date.desc(), HarvestBatch.id.desc())
    ).all()
    return {"items": [_harvest_payload(*row) for row in rows], "total": len(rows)}


def create_harvest_batch(payload, actor):
    _require_write_access(payload.farm_id, actor)
    cycle = db.session.get(CropCycle, payload.crop_cycle_id)
    if cycle is None:
        raise ApiError("种植周期不存在", 404, "CROP_CYCLE_NOT_FOUND", "cropCycleId")
    if cycle.farm_id != payload.farm_id:
        raise ApiError("种植周期不属于当前农场", 409, "CROP_CYCLE_FARM_MISMATCH", "cropCycleId")
    if cycle.status != "HARVESTING":
        raise ApiError("只有采收中周期才能登记采收批次", 409, "CROP_CYCLE_HARVEST_STATUS_INVALID")
    lower = cycle.actual_start_date or cycle.planned_start_date
    if payload.harvest_date < lower:
        raise ApiError("采收日期不能早于周期开始日期", 409, "HARVEST_DATE_BEFORE_START", "harvestDate")
    if payload.harvest_date > date.today():
        raise ApiError("采收日期不能晚于今天", 400, "HARVEST_DATE_IN_FUTURE", "harvestDate")
    if cycle.actual_end_date and payload.harvest_date > cycle.actual_end_date:
        raise ApiError("采收日期不能晚于周期结束日期", 409, "HARVEST_DATE_AFTER_END", "harvestDate")
    unit = db.session.get(Unit, payload.unit_id)
    if unit is None:
        raise ApiError("计量单位不存在", 404, "UNIT_NOT_FOUND", "unitId")
    warehouse = db.session.get(Warehouse, payload.warehouse_id)
    if warehouse is None:
        raise ApiError("仓库不存在", 404, "WAREHOUSE_NOT_FOUND", "warehouseId")
    if warehouse.farm_id != payload.farm_id:
        raise ApiError("仓库不属于当前农场", 409, "WAREHOUSE_FARM_MISMATCH", "warehouseId")
    if not warehouse.is_active:
        raise ApiError("仓库已停用", 409, "WAREHOUSE_DISABLED", "warehouseId")
    existing = db.session.scalar(select(HarvestBatch).where(HarvestBatch.crop_cycle_id == cycle.id, HarvestBatch.harvest_no == payload.harvest_no))
    if existing is not None:
        same = (existing.harvest_date == payload.harvest_date and existing.gross_weight == payload.gross_weight and existing.net_weight == payload.net_weight and existing.unit_id == payload.unit_id and existing.warehouse_id == payload.warehouse_id and existing.notes == payload.notes)
        if not same:
            raise ApiError("采收批号已存在且内容不同", 409, "HARVEST_NO_EXISTS", "harvestNo")
        return _harvest_payload(existing, unit, warehouse), False
    batch = HarvestBatch(farm_id=payload.farm_id, crop_cycle_id=cycle.id, harvest_no=payload.harvest_no, harvest_date=payload.harvest_date, gross_weight=payload.gross_weight, net_weight=payload.net_weight, unit_id=unit.id, warehouse_id=warehouse.id, notes=payload.notes, created_by_id=actor.id)
    db.session.add(batch)
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ApiError("采收批次登记冲突，请刷新后重试", 409, "HARVEST_CONFLICT") from error
    return _harvest_payload(batch, unit, warehouse), True


def _curing_payload(batch, unit):
    efficiency = batch.output_weight / batch.input_weight * 100 if batch.output_weight else None
    return {
        "id": batch.id, "farmId": batch.farm_id, "cropCycleId": batch.crop_cycle_id,
        "curingNo": batch.curing_no, "startAt": format_datetime(batch.start_at),
        "endAt": format_datetime(batch.end_at), "inputWeight": _decimal_text(batch.input_weight),
        "outputWeight": _decimal_text(batch.output_weight) if batch.output_weight else None,
        "unitId": batch.unit_id, "unitName": unit.name, "fuelCost": format(batch.fuel_cost, ".2f"),
        "electricityCost": format(batch.electricity_cost, ".2f"), "status": batch.status,
        "curingEfficiency": format(efficiency, ".2f") if efficiency is not None else None,
        "notes": batch.notes, "createdAt": format_datetime(batch.created_at),
    }


def _curing_cycle(farm_id, cycle_id):
    cycle = db.session.get(CropCycle, cycle_id)
    if cycle is None:
        raise ApiError("种植周期不存在", 404, "CROP_CYCLE_NOT_FOUND", "cropCycleId")
    if cycle.farm_id != farm_id:
        raise ApiError("种植周期不属于当前农场", 409, "CROP_CYCLE_FARM_MISMATCH", "cropCycleId")
    crop_type = db.session.get(CropType, cycle.crop_type_id)
    if crop_type.code != "TOBACCO":
        raise ApiError("只有烟草种植周期可以登记烘烤批次", 409, "CURING_CROP_TYPE_INVALID", "cropCycleId")
    return cycle


def list_tobacco_curing_batches(query, actor):
    get_accessible_farm(query.farm_id, actor)
    cycle = _curing_cycle(query.farm_id, query.crop_cycle_id)
    rows = db.session.execute(
        select(TobaccoCuringBatch, Unit).join(Unit, Unit.id == TobaccoCuringBatch.unit_id)
        .where(TobaccoCuringBatch.crop_cycle_id == cycle.id)
        .order_by(TobaccoCuringBatch.start_at.desc(), TobaccoCuringBatch.id.desc())
    ).all()
    return {"items": [_curing_payload(*row) for row in rows], "total": len(rows)}


def create_tobacco_curing_batch(payload, actor):
    _require_write_access(payload.farm_id, actor)
    cycle = _curing_cycle(payload.farm_id, payload.crop_cycle_id)
    if cycle.status != "HARVESTING":
        raise ApiError("只有采收中周期才能开始烘烤", 409, "CROP_CYCLE_CURING_STATUS_INVALID")
    if payload.start_at > datetime.now():
        raise ApiError("烘烤开始时间不能晚于当前时间", 400, "CURING_START_IN_FUTURE", "startAt")
    lower = cycle.actual_start_date or cycle.planned_start_date
    if payload.start_at.date() < lower:
        raise ApiError("烘烤开始时间不能早于周期开始日期", 409, "CURING_BEFORE_CYCLE", "startAt")
    unit = db.session.get(Unit, payload.unit_id)
    if unit is None:
        raise ApiError("计量单位不存在", 404, "UNIT_NOT_FOUND", "unitId")
    existing = db.session.scalar(select(TobaccoCuringBatch).where(TobaccoCuringBatch.crop_cycle_id == cycle.id, TobaccoCuringBatch.curing_no == payload.curing_no))
    if existing is not None:
        if existing.start_at != payload.start_at or existing.input_weight != payload.input_weight or existing.unit_id != unit.id or existing.notes != payload.notes:
            raise ApiError("烘烤批号已存在且内容不同", 409, "CURING_NO_EXISTS", "curingNo")
        return _curing_payload(existing, unit), False
    harvested = Decimal(db.session.scalar(select(func.coalesce(func.sum(HarvestBatch.net_weight), 0)).where(HarvestBatch.crop_cycle_id == cycle.id, HarvestBatch.unit_id == unit.id)) or 0)
    curing_input = Decimal(db.session.scalar(select(func.coalesce(func.sum(TobaccoCuringBatch.input_weight), 0)).where(TobaccoCuringBatch.crop_cycle_id == cycle.id, TobaccoCuringBatch.unit_id == unit.id)) or 0)
    available = harvested - curing_input
    if payload.input_weight > available:
        raise ApiError("入炉重量超过未烘烤采收净重", 409, "CURING_INPUT_EXCEEDS_HARVEST", "inputWeight", {"available": _decimal_text(max(available, Decimal("0")))})
    batch = TobaccoCuringBatch(farm_id=payload.farm_id, crop_cycle_id=cycle.id, curing_no=payload.curing_no, start_at=payload.start_at, input_weight=payload.input_weight, unit_id=unit.id, notes=payload.notes, created_by_id=actor.id)
    db.session.add(batch)
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ApiError("烘烤批次登记冲突，请刷新后重试", 409, "CURING_CONFLICT") from error
    return _curing_payload(batch, unit), True


def complete_tobacco_curing_batch(batch_id, payload, actor):
    batch = db.session.scalar(select(TobaccoCuringBatch).where(TobaccoCuringBatch.id == batch_id).with_for_update())
    if batch is None:
        raise ApiError("烘烤批次不存在", 404, "CURING_BATCH_NOT_FOUND")
    _require_write_access(batch.farm_id, actor)
    unit = db.session.get(Unit, batch.unit_id)
    if batch.status == "COMPLETED":
        if batch.end_at == payload.end_at and batch.output_weight == payload.output_weight and batch.fuel_cost == payload.fuel_cost and batch.electricity_cost == payload.electricity_cost:
            return _curing_payload(batch, unit)
        raise ApiError("烘烤批次已经完成", 409, "CURING_BATCH_COMPLETED")
    if payload.end_at < batch.start_at:
        raise ApiError("烘烤结束时间不能早于开始时间", 409, "CURING_END_BEFORE_START", "endAt")
    if payload.end_at > datetime.now():
        raise ApiError("烘烤结束时间不能晚于当前时间", 400, "CURING_END_IN_FUTURE", "endAt")
    if payload.output_weight > batch.input_weight:
        raise ApiError("出炉重量不能超过入炉重量", 409, "CURING_OUTPUT_EXCEEDS_INPUT", "outputWeight")
    batch.end_at, batch.output_weight = payload.end_at, payload.output_weight
    batch.fuel_cost, batch.electricity_cost = payload.fuel_cost, payload.electricity_cost
    batch.status, batch.completed_by_id = "COMPLETED", actor.id
    db.session.commit()
    return _curing_payload(batch, unit)
