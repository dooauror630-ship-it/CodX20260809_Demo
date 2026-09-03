from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from math import ceil

from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError

from ...core.errors import ApiError
from ...extensions import db
from ..auth.service import format_datetime
from ..catalog.models import LivestockSpecies
from ..farm.models import Barn
from ..farm.service import get_accessible_farm
from ..inventory.models import StockDocument, StockMovementLine
from ..inventory.purchase_service import _production_operation_payload, _require_write_access
from .models import CostEntry, LivestockBatch, LivestockHealthRecord, LivestockMovement, LivestockWeightRecord


REDUCTION_TYPES = ("DEATH", "CULL", "EXIT")


def _empty_state():
    return {
        "initial_count": 0,
        "death_count": 0,
        "cull_count": 0,
        "exit_count": 0,
        "movement_count": 0,
        "positions": defaultdict(int),
    }


def _batch_states(batch_ids):
    states = {batch_id: _empty_state() for batch_id in batch_ids}
    if not batch_ids:
        return states

    movements = db.session.scalars(
        select(LivestockMovement)
        .where(LivestockMovement.batch_id.in_(batch_ids))
        .order_by(LivestockMovement.occurred_on, LivestockMovement.id)
    ).all()
    barn_ids = {
        barn_id
        for movement in movements
        for barn_id in (movement.from_barn_id, movement.to_barn_id)
        if barn_id is not None
    }
    barns = {
        barn.id: barn
        for barn in db.session.scalars(select(Barn).where(Barn.id.in_(barn_ids))).all()
    } if barn_ids else {}

    for movement in movements:
        state = states[movement.batch_id]
        state["movement_count"] += 1
        if movement.to_barn_id is not None:
            state["positions"][movement.to_barn_id] += movement.quantity
        if movement.from_barn_id is not None:
            state["positions"][movement.from_barn_id] -= movement.quantity
        if movement.movement_type == "ENTRY":
            state["initial_count"] += movement.quantity
        elif movement.movement_type == "DEATH":
            state["death_count"] += movement.quantity
        elif movement.movement_type == "CULL":
            state["cull_count"] += movement.quantity
        elif movement.movement_type == "EXIT":
            state["exit_count"] += movement.quantity

    for state in states.values():
        state["current_head_count"] = sum(state["positions"].values())
        state["barn_balances"] = [
            {
                "barnId": barn_id,
                "barnCode": barns[barn_id].code,
                "barnName": barns[barn_id].name,
                "barnCapacity": barns[barn_id].capacity,
                "headCount": head_count,
            }
            for barn_id, head_count in sorted(
                state["positions"].items(),
                key=lambda item: (barns[item[0]].name, item[0]),
            )
            if head_count > 0 and barn_id in barns
        ]
    return states


def _batch_payload(batch, species, state):
    return {
        "id": batch.id,
        "farmId": batch.farm_id,
        "speciesId": species.id,
        "speciesCode": species.code,
        "speciesName": species.name,
        "batchNo": batch.batch_no,
        "name": batch.name,
        "entryDate": batch.entry_date.isoformat(),
        "source": batch.source,
        "status": batch.status,
        "closedAt": format_datetime(batch.closed_at),
        "notes": batch.notes,
        "initialCount": state["initial_count"],
        "currentHeadCount": state["current_head_count"],
        "deathCount": state["death_count"],
        "cullCount": state["cull_count"],
        "exitCount": state["exit_count"],
        "movementCount": state["movement_count"],
        "barnBalances": state["barn_balances"],
        "createdAt": format_datetime(batch.created_at),
        "updatedAt": format_datetime(batch.updated_at),
    }


def _movement_payload(movement, barns=None):
    barn_ids = {value for value in (movement.from_barn_id, movement.to_barn_id) if value is not None}
    if barns is None:
        barns = {
            barn.id: barn
            for barn in db.session.scalars(select(Barn).where(Barn.id.in_(barn_ids))).all()
        } if barn_ids else {}
    from_barn = barns.get(movement.from_barn_id)
    to_barn = barns.get(movement.to_barn_id)
    return {
        "id": movement.id,
        "farmId": movement.farm_id,
        "batchId": movement.batch_id,
        "movementNo": movement.movement_no,
        "movementType": movement.movement_type,
        "fromBarnId": movement.from_barn_id,
        "fromBarnCode": from_barn.code if from_barn else None,
        "fromBarnName": from_barn.name if from_barn else None,
        "toBarnId": movement.to_barn_id,
        "toBarnCode": to_barn.code if to_barn else None,
        "toBarnName": to_barn.name if to_barn else None,
        "quantity": movement.quantity,
        "occurredOn": movement.occurred_on.isoformat(),
        "reason": movement.reason,
        "notes": movement.notes,
        "createdById": movement.created_by_id,
        "createdAt": format_datetime(movement.created_at),
    }


def _health_payload(record):
    return {
        "id": record.id,
        "farmId": record.farm_id,
        "batchId": record.batch_id,
        "recordNo": record.record_no,
        "recordType": record.record_type,
        "occurredOn": record.occurred_on.isoformat(),
        "description": record.description,
        "medicineName": record.medicine_name,
        "dosage": record.dosage,
        "notes": record.notes,
        "createdById": record.created_by_id,
        "createdAt": format_datetime(record.created_at),
    }


def _weight_payload(record):
    return {
        "id": record.id,
        "farmId": record.farm_id,
        "batchId": record.batch_id,
        "recordNo": record.record_no,
        "occurredOn": record.occurred_on.isoformat(),
        "sampleCount": record.sample_count,
        "averageWeight": format(record.average_weight, "f").rstrip("0").rstrip("."),
        "notes": record.notes,
        "createdById": record.created_by_id,
        "createdAt": format_datetime(record.created_at),
    }


def _cost_entry_payload(entry):
    return {
        "id": entry.id,
        "farmId": entry.farm_id,
        "batchId": entry.livestock_batch_id,
        "entryNo": entry.entry_no,
        "businessDate": entry.business_date.isoformat(),
        "costType": entry.cost_type,
        "amount": format(entry.amount, ".2f"),
        "description": entry.description,
        "notes": entry.notes,
        "status": entry.status,
        "cancelledAt": format_datetime(entry.cancelled_at),
        "cancelledById": entry.cancelled_by_id,
        "createdById": entry.created_by_id,
        "createdAt": format_datetime(entry.created_at),
    }


def _farm_summary(farm_id):
    active_batch_count = db.session.scalar(
        select(func.count(LivestockBatch.id)).where(
            LivestockBatch.farm_id == farm_id,
            LivestockBatch.status == "ACTIVE",
        )
    ) or 0
    row = db.session.execute(
        select(
            func.coalesce(func.sum(case(
                (LivestockMovement.movement_type == "ENTRY", LivestockMovement.quantity),
                else_=0,
            )), 0),
            func.coalesce(func.sum(case(
                (LivestockMovement.movement_type == "DEATH", LivestockMovement.quantity),
                else_=0,
            )), 0),
            func.coalesce(func.sum(case(
                (LivestockMovement.movement_type == "CULL", LivestockMovement.quantity),
                else_=0,
            )), 0),
            func.coalesce(func.sum(case(
                (LivestockMovement.movement_type == "EXIT", LivestockMovement.quantity),
                else_=0,
            )), 0),
        ).where(LivestockMovement.farm_id == farm_id)
    ).one()
    initial_count, death_count, cull_count, exit_count = (int(value) for value in row)
    return {
        "activeBatchCount": active_batch_count,
        "currentHeadCount": initial_count - death_count - cull_count - exit_count,
        "deathCount": death_count,
        "exitedCount": cull_count + exit_count,
    }


def list_livestock_batches(query, actor):
    get_accessible_farm(query.farm_id, actor)
    conditions = [LivestockBatch.farm_id == query.farm_id]
    if query.keyword:
        conditions.append(or_(
            LivestockBatch.batch_no.contains(query.keyword, autoescape=True),
            LivestockBatch.name.contains(query.keyword, autoescape=True),
            LivestockBatch.source.contains(query.keyword, autoescape=True),
        ))
    if query.status != "all":
        conditions.append(LivestockBatch.status == query.status)

    total = db.session.scalar(select(func.count(LivestockBatch.id)).where(*conditions)) or 0
    rows = db.session.execute(
        select(LivestockBatch, LivestockSpecies)
        .join(LivestockSpecies, LivestockSpecies.id == LivestockBatch.species_id)
        .where(*conditions)
        .order_by(LivestockBatch.status.asc(), LivestockBatch.entry_date.desc(), LivestockBatch.id.desc())
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
    ).all()
    states = _batch_states([batch.id for batch, _species in rows])
    return {
        "items": [_batch_payload(batch, species, states[batch.id]) for batch, species in rows],
        "pagination": {
            "page": query.page,
            "pageSize": query.page_size,
            "total": total,
            "totalPages": ceil(total / query.page_size) if total else 0,
        },
        "summary": _farm_summary(query.farm_id),
    }


def _get_batch(batch_id):
    batch = db.session.get(LivestockBatch, batch_id)
    if batch is None:
        raise ApiError("养殖批次不存在", 404, "LIVESTOCK_BATCH_NOT_FOUND")
    return batch


def _signed_operation_amount(record):
    amount = Decimal(record["amount"])
    return amount if record["operationType"] == "issue" else -amount


def _cost_category(item_type):
    if item_type in ("feed", "veterinary_drug", "supply"):
        return item_type
    return "other"


def _production_trend(batch, movements, weight_records, production_records):
    movement_by_date = defaultdict(int)
    for movement in movements:
        if movement.movement_type == "ENTRY":
            movement_by_date[movement.occurred_on] += movement.quantity
        elif movement.movement_type in REDUCTION_TYPES:
            movement_by_date[movement.occurred_on] -= movement.quantity

    weight_by_date = {
        record.occurred_on: record
        for record in sorted(weight_records, key=lambda item: (item.occurred_on, item.id))
    }
    cost_by_date = defaultdict(Decimal)
    for record in production_records:
        cost_by_date[date.fromisoformat(record["operationDate"])] += _signed_operation_amount(record)

    dates = sorted({batch.entry_date, *movement_by_date, *weight_by_date, *cost_by_date})
    head_count = 0
    cumulative_cost = Decimal("0")
    trend = []
    for current_date in dates:
        head_count += movement_by_date[current_date]
        daily_cost = cost_by_date[current_date]
        cumulative_cost += daily_cost
        weight = weight_by_date.get(current_date)
        trend.append({
            "date": current_date.isoformat(),
            "headCount": head_count,
            "averageWeight": _weight_payload(weight)["averageWeight"] if weight else None,
            "sampleCount": weight.sample_count if weight else None,
            "dailyDirectCost": format(daily_cost, ".2f"),
            "cumulativeDirectCost": format(cumulative_cost, ".2f"),
        })
    return trend


def livestock_batch_detail(batch_id, actor):
    batch = _get_batch(batch_id)
    get_accessible_farm(batch.farm_id, actor)
    species = db.session.get(LivestockSpecies, batch.species_id)
    state = _batch_states([batch.id])[batch.id]
    movements = db.session.scalars(
        select(LivestockMovement)
        .where(LivestockMovement.batch_id == batch.id)
        .order_by(LivestockMovement.occurred_on.desc(), LivestockMovement.id.desc())
    ).all()
    barn_ids = {
        barn_id
        for movement in movements
        for barn_id in (movement.from_barn_id, movement.to_barn_id)
        if barn_id is not None
    }
    barns = {
        barn.id: barn
        for barn in db.session.scalars(select(Barn).where(Barn.id.in_(barn_ids))).all()
    } if barn_ids else {}
    health_records = db.session.scalars(
        select(LivestockHealthRecord)
        .where(LivestockHealthRecord.batch_id == batch.id)
        .order_by(LivestockHealthRecord.occurred_on.desc(), LivestockHealthRecord.id.desc())
    ).all()
    weight_records = db.session.scalars(
        select(LivestockWeightRecord)
        .where(LivestockWeightRecord.batch_id == batch.id)
        .order_by(LivestockWeightRecord.occurred_on.desc(), LivestockWeightRecord.id.desc())
    ).all()
    cost_entries = db.session.scalars(
        select(CostEntry)
        .where(CostEntry.livestock_batch_id == batch.id)
        .order_by(CostEntry.business_date.desc(), CostEntry.id.desc())
    ).all()
    production_documents = db.session.scalars(
        select(StockDocument)
        .join(StockMovementLine, StockMovementLine.stock_document_id == StockDocument.id)
        .where(
            StockDocument.status == "POSTED",
            StockMovementLine.cost_object_type == "LIVESTOCK_BATCH",
            StockMovementLine.cost_object_id == batch.id,
        )
        .distinct()
        .order_by(StockDocument.occurred_at.desc(), StockDocument.id.desc())
    ).all()
    production_records = [_production_operation_payload(document) for document in production_documents]
    feeding_records = [
        record
        for record in production_records
        if record["itemType"] == "feed"
    ]
    cost_totals = defaultdict(Decimal)
    cost_counts = defaultdict(int)
    for record in production_records:
        category = _cost_category(record["itemType"])
        cost_totals[category] += _signed_operation_amount(record)
        cost_counts[category] += 1
    total_feed_cost = cost_totals["feed"]
    total_direct_cost = sum(cost_totals.values(), Decimal("0"))
    additional_cost_totals = defaultdict(Decimal)
    additional_cost_counts = defaultdict(int)
    for entry in cost_entries:
        if entry.status == "POSTED":
            additional_cost_totals[entry.cost_type] += entry.amount
            additional_cost_counts[entry.cost_type] += 1
    total_additional_cost = sum(additional_cost_totals.values(), Decimal("0"))
    total_production_cost = total_direct_cost + total_additional_cost
    use_exited_cost_basis = batch.status == "CLOSED" and state["exit_count"] > 0
    cost_basis_count = state["exit_count"] if use_exited_cost_basis else state["current_head_count"]
    cost_per_head = total_direct_cost / cost_basis_count if cost_basis_count > 0 else None
    production_cost_per_head = total_production_cost / cost_basis_count if cost_basis_count > 0 else None
    cost_per_head_basis = "EXITED" if use_exited_cost_basis else "CURRENT_ESTIMATE"
    feed_weight_complete = all(record["unitDimension"] == "WEIGHT" for record in feeding_records)
    total_feed_weight = sum(
        (
            Decimal(record["quantity"]) * Decimal(record["unitBaseFactor"])
            if record["operationType"] == "issue"
            else -Decimal(record["quantity"]) * Decimal(record["unitBaseFactor"])
        )
        for record in feeding_records
        if record["unitDimension"] == "WEIGHT"
    )
    chronological_weights = sorted(weight_records, key=lambda item: (item.occurred_on, item.id))
    adg = None
    estimated_weight_gain = None
    fcr = None
    if len(chronological_weights) >= 2:
        first, latest = chronological_weights[0], chronological_weights[-1]
        days = (latest.occurred_on - first.occurred_on).days
        if days > 0:
            adg = format((latest.average_weight - first.average_weight) / days, ".3f")
        weight_gain_per_head = latest.average_weight - first.average_weight
        estimated_growth_head_count = state["initial_count"] - state["death_count"]
        if weight_gain_per_head > 0 and estimated_growth_head_count > 0:
            estimated_weight_gain = weight_gain_per_head * estimated_growth_head_count
            if feed_weight_complete and total_feed_weight > 0:
                fcr = format(total_feed_weight / estimated_weight_gain, ".3f")
    latest_weight = chronological_weights[-1] if chronological_weights else None
    return {
        **_batch_payload(batch, species, state),
        "movements": [_movement_payload(movement, barns) for movement in movements],
        "healthRecords": [_health_payload(record) for record in health_records],
        "weightRecords": [_weight_payload(record) for record in weight_records],
        "feedingRecords": feeding_records,
        "materialRecords": production_records,
        "costEntries": [_cost_entry_payload(entry) for entry in cost_entries],
        "productionTrend": _production_trend(batch, movements, weight_records, production_records),
        "productionSummary": {
            "totalFeedCost": format(total_feed_cost, ".2f"),
            "totalDirectCost": format(total_direct_cost, ".2f"),
            "costPerHead": format(cost_per_head, ".2f") if cost_per_head is not None else None,
            "costPerHeadBasis": cost_per_head_basis if cost_per_head is not None else None,
            "totalAdditionalCost": format(total_additional_cost, ".2f"),
            "totalProductionCost": format(total_production_cost, ".2f"),
            "productionCostPerHead": (
                format(production_cost_per_head, ".2f") if production_cost_per_head is not None else None
            ),
            "productionCostPerHeadBasis": cost_per_head_basis if production_cost_per_head is not None else None,
            "additionalCostBreakdown": [
                {
                    "costType": cost_type,
                    "amount": format(additional_cost_totals[cost_type], ".2f"),
                    "recordCount": additional_cost_counts[cost_type],
                }
                for cost_type in ("ENTRY", "LABOR", "OVERHEAD", "OTHER")
                if additional_cost_counts[cost_type]
            ],
            "costBreakdown": [
                {
                    "category": category,
                    "amount": format(cost_totals[category], ".2f"),
                    "recordCount": cost_counts[category],
                }
                for category in ("feed", "veterinary_drug", "supply", "other")
                if cost_counts[category]
            ],
            "totalFeedWeightKg": format(total_feed_weight, ".3f"),
            "latestAverageWeight": _weight_payload(latest_weight)["averageWeight"] if latest_weight else None,
            "latestWeightDate": latest_weight.occurred_on.isoformat() if latest_weight else None,
            "adg": adg,
            "estimatedWeightGainKg": format(estimated_weight_gain, ".3f") if estimated_weight_gain else None,
            "fcr": fcr,
            "fcrEstimated": fcr is not None,
            "feedWeightComplete": feed_weight_complete,
            "healthRecordCount": len(health_records),
        },
    }


def livestock_analysis(query, actor, today=None):
    get_accessible_farm(query.farm_id, actor)
    today = today or date.today()
    pig_species_id = db.session.scalar(
        select(LivestockSpecies.id).where(LivestockSpecies.code == "PIG")
    )
    batches = db.session.scalars(
        select(LivestockBatch)
        .where(
            LivestockBatch.farm_id == query.farm_id,
            LivestockBatch.species_id == pig_species_id,
        )
        .order_by(LivestockBatch.entry_date.desc(), LivestockBatch.id.desc())
    ).all() if pig_species_id else []
    batch_ids = [batch.id for batch in batches]
    movements = db.session.scalars(
        select(LivestockMovement)
        .where(
            LivestockMovement.batch_id.in_(batch_ids),
            LivestockMovement.occurred_on <= today,
        )
        .order_by(LivestockMovement.occurred_on, LivestockMovement.id)
    ).all() if batch_ids else []

    entry_count = sum(movement.quantity for movement in movements if movement.movement_type == "ENTRY")
    death_count = sum(movement.quantity for movement in movements if movement.movement_type == "DEATH")
    reduction_count = sum(
        movement.quantity for movement in movements if movement.movement_type in REDUCTION_TYPES
    )
    mortality_rate = Decimal(death_count * 100) / entry_count if entry_count else Decimal("0")

    start_date = today - timedelta(days=query.trend_days - 1)
    opening_head_count = 0
    movement_by_date = defaultdict(int)
    death_by_date = defaultdict(int)
    for movement in movements:
        quantity_delta = 0
        if movement.movement_type == "ENTRY":
            quantity_delta = movement.quantity
        elif movement.movement_type in REDUCTION_TYPES:
            quantity_delta = -movement.quantity
        if movement.occurred_on < start_date:
            opening_head_count += quantity_delta
        else:
            movement_by_date[movement.occurred_on] += quantity_delta
            if movement.movement_type == "DEATH":
                death_by_date[movement.occurred_on] += movement.quantity

    trend = []
    head_count = opening_head_count
    for offset in range(query.trend_days):
        current_date = start_date + timedelta(days=offset)
        head_count += movement_by_date[current_date]
        trend.append({
            "date": current_date.isoformat(),
            "currentHeadCount": head_count,
            "deathCount": death_by_date[current_date],
        })

    comparisons = []
    for batch in batches[:10]:
        detail = livestock_batch_detail(batch.id, actor)
        production = detail["productionSummary"]
        batch_mortality_rate = (
            Decimal(detail["deathCount"] * 100) / detail["initialCount"]
            if detail["initialCount"]
            else Decimal("0")
        )
        comparisons.append({
            "batchId": batch.id,
            "batchNo": batch.batch_no,
            "name": batch.name,
            "status": batch.status,
            "entryDate": batch.entry_date.isoformat(),
            "initialCount": detail["initialCount"],
            "currentHeadCount": detail["currentHeadCount"],
            "deathCount": detail["deathCount"],
            "mortalityRate": format(batch_mortality_rate, ".2f"),
            "latestAverageWeight": production["latestAverageWeight"],
            "adg": production["adg"],
            "fcr": production["fcr"],
            "fcrEstimated": production["fcrEstimated"],
            "directCost": production["totalDirectCost"],
            "costPerHead": production["costPerHead"],
            "productionCost": production["totalProductionCost"],
            "productionCostPerHead": production["productionCostPerHead"],
        })

    return {
        "summary": {
            "activeBatchCount": sum(batch.status == "ACTIVE" for batch in batches),
            "currentHeadCount": entry_count - reduction_count,
            "entryCount": entry_count,
            "deathCount": death_count,
            "mortalityRate": format(mortality_rate, ".2f"),
        },
        "trend": trend,
        "batchComparisons": comparisons,
        "period": {
            "dateFrom": start_date.isoformat(),
            "dateTo": today.isoformat(),
            "trendDays": query.trend_days,
        },
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
    }


def create_livestock_cost_entry(payload, actor):
    _require_write_access(payload.farm_id, actor)
    existing = db.session.scalar(select(CostEntry).where(
        CostEntry.farm_id == payload.farm_id,
        CostEntry.entry_no == payload.entry_no,
    ))
    if existing is not None:
        matches = all((
            existing.livestock_batch_id == payload.batch_id,
            existing.business_date == payload.business_date,
            existing.cost_type == payload.cost_type,
            existing.amount == payload.amount,
            existing.description == payload.description,
            existing.notes == payload.notes,
        ))
        if not matches:
            raise ApiError("成本记录单号已存在且内容不同", 409, "LIVESTOCK_COST_NO_EXISTS", "entryNo")
        return _cost_entry_payload(existing), False

    batch = _get_batch(payload.batch_id)
    if batch.farm_id != payload.farm_id:
        raise ApiError("养殖批次不属于当前农场", 409, "LIVESTOCK_BATCH_FARM_MISMATCH", "batchId")
    if payload.business_date < batch.entry_date:
        raise ApiError("成本日期不能早于入栏日期", 409, "LIVESTOCK_COST_BEFORE_ENTRY", "businessDate")
    if payload.business_date > date.today():
        raise ApiError("成本日期不能晚于今天", 400, "LIVESTOCK_COST_IN_FUTURE", "businessDate")
    if batch.closed_at and payload.business_date > batch.closed_at.date():
        raise ApiError("成本日期不能晚于批次结束日期", 409, "LIVESTOCK_COST_AFTER_CLOSE", "businessDate")

    entry = CostEntry(
        farm_id=payload.farm_id,
        livestock_batch_id=payload.batch_id,
        entry_no=payload.entry_no,
        business_date=payload.business_date,
        cost_type=payload.cost_type,
        amount=payload.amount,
        description=payload.description,
        notes=payload.notes,
        created_by_id=actor.id,
    )
    db.session.add(entry)
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ApiError("成本记录登记冲突，请刷新后重试", 409, "LIVESTOCK_COST_CONFLICT") from error
    return _cost_entry_payload(entry), True


def cancel_livestock_cost_entry(entry_id, actor):
    entry = db.session.scalar(select(CostEntry).where(CostEntry.id == entry_id).with_for_update())
    if entry is None:
        raise ApiError("成本记录不存在", 404, "LIVESTOCK_COST_NOT_FOUND")
    _require_write_access(entry.farm_id, actor)
    if entry.status == "CANCELLED":
        return _cost_entry_payload(entry)
    entry.status = "CANCELLED"
    entry.cancelled_at = datetime.now()
    entry.cancelled_by_id = actor.id
    db.session.commit()
    return _cost_entry_payload(entry)


def _pig_species(species_id):
    species = db.session.get(LivestockSpecies, species_id)
    if species is None:
        raise ApiError("养殖品类不存在", 404, "LIVESTOCK_SPECIES_NOT_FOUND", "speciesId")
    if not species.is_active:
        raise ApiError("养殖品类已停用", 409, "LIVESTOCK_SPECIES_DISABLED", "speciesId")
    if species.code != "PIG":
        raise ApiError("当前阶段仅支持生猪批次", 409, "LIVESTOCK_SPECIES_NOT_SUPPORTED", "speciesId")
    return species


def _lock_barns(barn_ids, farm_id):
    unique_ids = sorted(set(barn_ids))
    barns = db.session.scalars(
        select(Barn).where(Barn.id.in_(unique_ids)).order_by(Barn.id).with_for_update()
    ).all()
    by_id = {barn.id: barn for barn in barns}
    if len(by_id) != len(unique_ids):
        raise ApiError("圈舍不存在", 404, "BARN_NOT_FOUND")
    if any(barn.farm_id != farm_id for barn in barns):
        raise ApiError("不能引用其他农场的圈舍", 409, "BARN_FARM_MISMATCH")
    return by_id


def _validate_pig_barn(barn, *, destination=False):
    if barn.barn_type not in ("pig", "isolation"):
        raise ApiError("生猪只能进入猪舍或隔离舍", 409, "BARN_TYPE_MISMATCH")
    if destination and not barn.is_active:
        raise ApiError("目标圈舍已停用", 409, "BARN_DISABLED")


def _barn_occupancy(farm_id, barn_id):
    arrivals = func.coalesce(func.sum(case(
        (LivestockMovement.to_barn_id == barn_id, LivestockMovement.quantity),
        else_=0,
    )), 0)
    departures = func.coalesce(func.sum(case(
        (LivestockMovement.from_barn_id == barn_id, LivestockMovement.quantity),
        else_=0,
    )), 0)
    return int(db.session.scalar(
        select(arrivals - departures).where(LivestockMovement.farm_id == farm_id)
    ) or 0)


def _ensure_capacity(barn, incoming_count, farm_id):
    if barn.capacity <= 0:
        return
    current = _barn_occupancy(farm_id, barn.id)
    if current + incoming_count > barn.capacity:
        raise ApiError(
            f"圈舍容量不足，当前 {current}，可用 {barn.capacity - current}",
            409,
            "BARN_CAPACITY_EXCEEDED",
            "quantity",
            {"current": current, "capacity": barn.capacity, "available": barn.capacity - current},
        )


def _existing_batch(payload, actor):
    batch = db.session.scalar(select(LivestockBatch).where(
        LivestockBatch.farm_id == payload.farm_id,
        LivestockBatch.batch_no == payload.batch_no,
    ))
    entry = db.session.scalar(select(LivestockMovement).where(
        LivestockMovement.farm_id == payload.farm_id,
        LivestockMovement.movement_no == payload.entry_no,
    ))
    if batch is None and entry is None:
        return None
    if batch is None or entry is None or entry.batch_id != batch.id:
        raise ApiError("批次编号或入栏单号已被使用", 409, "LIVESTOCK_ENTRY_NO_EXISTS")
    matches = (
        batch.species_id == payload.species_id
        and batch.name == payload.name
        and batch.entry_date == payload.entry_date
        and batch.source == payload.source
        and batch.notes == payload.notes
        and entry.movement_type == "ENTRY"
        and entry.to_barn_id == payload.barn_id
        and entry.quantity == payload.initial_count
        and entry.occurred_on == payload.entry_date
    )
    if not matches:
        raise ApiError("批次编号或入栏单号已存在且内容不同", 409, "LIVESTOCK_ENTRY_NO_EXISTS")
    return livestock_batch_detail(batch.id, actor)


def create_livestock_batch(payload, actor):
    _require_write_access(payload.farm_id, actor)
    existing = _existing_batch(payload, actor)
    if existing is not None:
        return existing, False
    if payload.entry_date > date.today():
        raise ApiError("入栏日期不能晚于今天", 400, "ENTRY_DATE_IN_FUTURE", "entryDate")
    _pig_species(payload.species_id)
    barn = _lock_barns([payload.barn_id], payload.farm_id)[payload.barn_id]
    _validate_pig_barn(barn, destination=True)
    _ensure_capacity(barn, payload.initial_count, payload.farm_id)

    batch = LivestockBatch(
        farm_id=payload.farm_id,
        species_id=payload.species_id,
        batch_no=payload.batch_no,
        name=payload.name,
        entry_date=payload.entry_date,
        source=payload.source,
        notes=payload.notes,
        created_by_id=actor.id,
        updated_by_id=actor.id,
    )
    db.session.add(batch)
    try:
        db.session.flush()
        db.session.add(LivestockMovement(
            farm_id=payload.farm_id,
            batch_id=batch.id,
            movement_no=payload.entry_no,
            movement_type="ENTRY",
            to_barn_id=barn.id,
            quantity=payload.initial_count,
            occurred_on=payload.entry_date,
            created_by_id=actor.id,
        ))
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        existing = _existing_batch(payload, actor)
        if existing is not None:
            return existing, False
        raise ApiError("生猪批次入栏冲突，请刷新后重试", 409, "LIVESTOCK_ENTRY_CONFLICT") from error
    return livestock_batch_detail(batch.id, actor), True


def _movement_matches(movement, payload):
    return (
        movement.batch_id == payload.batch_id
        and movement.movement_type == payload.movement_type
        and movement.occurred_on == payload.occurred_on
        and movement.from_barn_id == payload.from_barn_id
        and movement.to_barn_id == payload.to_barn_id
        and movement.quantity == payload.quantity
        and movement.reason == payload.reason
        and movement.notes == payload.notes
    )


def _existing_movement(payload, actor):
    movement = db.session.scalar(select(LivestockMovement).where(
        LivestockMovement.farm_id == payload.farm_id,
        LivestockMovement.movement_no == payload.movement_no,
    ))
    if movement is None:
        return None
    if not _movement_matches(movement, payload):
        raise ApiError("存栏变动单号已存在且内容不同", 409, "LIVESTOCK_MOVEMENT_NO_EXISTS", "movementNo")
    return _movement_payload(movement), livestock_batch_detail(movement.batch_id, actor)


def create_livestock_movement(payload, actor):
    _require_write_access(payload.farm_id, actor)
    existing = _existing_movement(payload, actor)
    if existing is not None:
        return *existing, False

    batch = db.session.scalar(
        select(LivestockBatch).where(LivestockBatch.id == payload.batch_id).with_for_update()
    )
    if batch is None:
        raise ApiError("养殖批次不存在", 404, "LIVESTOCK_BATCH_NOT_FOUND")
    if batch.farm_id != payload.farm_id:
        raise ApiError("养殖批次不属于当前农场", 409, "LIVESTOCK_BATCH_FARM_MISMATCH")
    if batch.status != "ACTIVE":
        raise ApiError("批次已结束，不能继续登记存栏变动", 409, "LIVESTOCK_BATCH_CLOSED")
    if payload.occurred_on > date.today():
        raise ApiError("变动日期不能晚于今天", 400, "MOVEMENT_DATE_IN_FUTURE", "occurredOn")
    latest_date = db.session.scalar(
        select(func.max(LivestockMovement.occurred_on)).where(LivestockMovement.batch_id == batch.id)
    )
    if payload.occurred_on < batch.entry_date or (latest_date and payload.occurred_on < latest_date):
        raise ApiError(
            "变动日期不能早于批次最近一条流水日期",
            409,
            "MOVEMENT_DATE_BEFORE_LATEST",
            "occurredOn",
            {"latestDate": latest_date.isoformat() if latest_date else batch.entry_date.isoformat()},
        )

    barn_ids = [payload.from_barn_id]
    if payload.to_barn_id is not None:
        barn_ids.append(payload.to_barn_id)
    barns = _lock_barns(barn_ids, payload.farm_id)
    source_barn = barns[payload.from_barn_id]
    _validate_pig_barn(source_barn)
    if payload.to_barn_id is not None:
        destination_barn = barns[payload.to_barn_id]
        _validate_pig_barn(destination_barn, destination=True)
        _ensure_capacity(destination_barn, payload.quantity, payload.farm_id)

    state = _batch_states([batch.id])[batch.id]
    available = state["positions"].get(payload.from_barn_id, 0)
    if available < payload.quantity:
        raise ApiError(
            f"来源圈舍存栏不足，可用 {available} 头",
            409,
            "BARN_HEAD_COUNT_INSUFFICIENT",
            "quantity",
            {"available": available},
        )

    movement = LivestockMovement(
        farm_id=payload.farm_id,
        batch_id=batch.id,
        movement_no=payload.movement_no,
        movement_type=payload.movement_type,
        from_barn_id=payload.from_barn_id,
        to_barn_id=payload.to_barn_id,
        quantity=payload.quantity,
        occurred_on=payload.occurred_on,
        reason=payload.reason,
        notes=payload.notes,
        created_by_id=actor.id,
    )
    db.session.add(movement)
    if payload.movement_type in REDUCTION_TYPES and state["current_head_count"] == payload.quantity:
        batch.status = "CLOSED"
        batch.closed_at = datetime.combine(payload.occurred_on, time.min)
    batch.updated_by_id = actor.id
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        existing = _existing_movement(payload, actor)
        if existing is not None:
            return *existing, False
        raise ApiError("存栏变动登记冲突，请刷新后重试", 409, "LIVESTOCK_MOVEMENT_CONFLICT") from error
    return _movement_payload(movement), livestock_batch_detail(batch.id, actor), True


def _validate_production_record_batch(payload):
    batch = _get_batch(payload.batch_id)
    if batch.farm_id != payload.farm_id:
        raise ApiError("养殖批次不属于当前农场", 409, "LIVESTOCK_BATCH_FARM_MISMATCH", "batchId")
    if batch.status != "ACTIVE":
        raise ApiError("批次已结束，不能继续登记生产记录", 409, "LIVESTOCK_BATCH_CLOSED")
    if payload.occurred_on < batch.entry_date:
        raise ApiError("记录日期不能早于入栏日期", 409, "LIVESTOCK_RECORD_BEFORE_ENTRY", "occurredOn")
    if payload.occurred_on > date.today():
        raise ApiError("记录日期不能晚于今天", 400, "LIVESTOCK_RECORD_IN_FUTURE", "occurredOn")
    return batch


def create_livestock_health_record(payload, actor):
    _require_write_access(payload.farm_id, actor)
    existing = db.session.scalar(select(LivestockHealthRecord).where(
        LivestockHealthRecord.farm_id == payload.farm_id,
        LivestockHealthRecord.record_no == payload.record_no,
    ))
    if existing is not None:
        matches = all((
            existing.batch_id == payload.batch_id,
            existing.record_type == payload.record_type,
            existing.occurred_on == payload.occurred_on,
            existing.description == payload.description,
            existing.medicine_name == payload.medicine_name,
            existing.dosage == payload.dosage,
            existing.notes == payload.notes,
        ))
        if not matches:
            raise ApiError("健康记录编号已存在且内容不同", 409, "LIVESTOCK_HEALTH_NO_EXISTS", "recordNo")
        return _health_payload(existing), False
    _validate_production_record_batch(payload)
    record = LivestockHealthRecord(
        farm_id=payload.farm_id,
        batch_id=payload.batch_id,
        record_no=payload.record_no,
        record_type=payload.record_type,
        occurred_on=payload.occurred_on,
        description=payload.description,
        medicine_name=payload.medicine_name,
        dosage=payload.dosage,
        notes=payload.notes,
        created_by_id=actor.id,
    )
    db.session.add(record)
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ApiError("健康记录登记冲突，请刷新后重试", 409, "LIVESTOCK_HEALTH_CONFLICT") from error
    return _health_payload(record), True


def create_livestock_weight_record(payload, actor):
    _require_write_access(payload.farm_id, actor)
    existing = db.session.scalar(select(LivestockWeightRecord).where(
        LivestockWeightRecord.farm_id == payload.farm_id,
        LivestockWeightRecord.record_no == payload.record_no,
    ))
    if existing is not None:
        matches = all((
            existing.batch_id == payload.batch_id,
            existing.occurred_on == payload.occurred_on,
            existing.sample_count == payload.sample_count,
            existing.average_weight == payload.average_weight,
            existing.notes == payload.notes,
        ))
        if not matches:
            raise ApiError("称重记录编号已存在且内容不同", 409, "LIVESTOCK_WEIGHT_NO_EXISTS", "recordNo")
        return _weight_payload(existing), False
    _validate_production_record_batch(payload)
    record = LivestockWeightRecord(
        farm_id=payload.farm_id,
        batch_id=payload.batch_id,
        record_no=payload.record_no,
        occurred_on=payload.occurred_on,
        sample_count=payload.sample_count,
        average_weight=payload.average_weight,
        notes=payload.notes,
        created_by_id=actor.id,
    )
    db.session.add(record)
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ApiError("称重记录登记冲突，请刷新后重试", 409, "LIVESTOCK_WEIGHT_CONFLICT") from error
    return _weight_payload(record), True
