from flask import Blueprint, g, request

from ...core.errors import success_response
from ...core.security import login_required
from ..auth.schemas import parse_payload
from .schemas import (
    CreateLivestockBatchPayload,
    CreateLivestockCostEntryPayload,
    CreateLivestockHealthRecordPayload,
    CreateLivestockMovementPayload,
    CreateLivestockWeightRecordPayload,
    LivestockAnalysisQuery,
    LivestockBatchListQuery,
)
from .service import (
    create_livestock_batch,
    cancel_livestock_cost_entry,
    create_livestock_cost_entry,
    create_livestock_health_record,
    create_livestock_movement,
    create_livestock_weight_record,
    livestock_analysis,
    livestock_batch_detail,
    list_livestock_batches,
)


livestock_bp = Blueprint("livestock", __name__)


@livestock_bp.get("/livestock-batches")
@login_required
def livestock_batches():
    query = parse_payload(LivestockBatchListQuery, request.args.to_dict(), "养殖批次筛选条件格式错误")
    return success_response(list_livestock_batches(query, g.current_user))


@livestock_bp.get("/livestock-analysis")
@login_required
def livestock_analysis_overview():
    query = parse_payload(LivestockAnalysisQuery, request.args.to_dict(), "养殖分析筛选条件格式错误")
    return success_response(livestock_analysis(query, g.current_user))


@livestock_bp.get("/livestock-batches/<int:batch_id>")
@login_required
def livestock_batch(batch_id):
    return success_response({"batch": livestock_batch_detail(batch_id, g.current_user)})


@livestock_bp.post("/livestock-batches")
@login_required
def add_livestock_batch():
    payload = parse_payload(CreateLivestockBatchPayload, request.get_json(silent=True), "养殖批次入栏信息格式错误")
    batch, created = create_livestock_batch(payload, g.current_user)
    return success_response(
        {"batch": batch},
        "养殖批次已入栏" if created else "该养殖批次已入栏",
        201 if created else 200,
    )


@livestock_bp.post("/livestock-movements")
@login_required
def add_livestock_movement():
    payload = parse_payload(CreateLivestockMovementPayload, request.get_json(silent=True), "养殖存栏变动信息格式错误")
    movement, batch, created = create_livestock_movement(payload, g.current_user)
    return success_response(
        {"movement": movement, "batch": batch},
        "存栏变动已登记" if created else "该存栏变动已登记",
        201 if created else 200,
    )


@livestock_bp.post("/livestock-health-records")
@login_required
def add_livestock_health_record():
    payload = parse_payload(CreateLivestockHealthRecordPayload, request.get_json(silent=True), "养殖健康记录格式错误")
    record, created = create_livestock_health_record(payload, g.current_user)
    return success_response(
        {"record": record},
        "健康记录已登记" if created else "该健康记录已登记",
        201 if created else 200,
    )


@livestock_bp.post("/livestock-weight-records")
@login_required
def add_livestock_weight_record():
    payload = parse_payload(CreateLivestockWeightRecordPayload, request.get_json(silent=True), "养殖称重记录格式错误")
    record, created = create_livestock_weight_record(payload, g.current_user)
    return success_response(
        {"record": record},
        "称重记录已登记" if created else "该称重记录已登记",
        201 if created else 200,
    )


@livestock_bp.post("/livestock-cost-entries")
@login_required
def add_livestock_cost_entry():
    payload = parse_payload(CreateLivestockCostEntryPayload, request.get_json(silent=True), "养殖成本记录格式错误")
    entry, created = create_livestock_cost_entry(payload, g.current_user)
    return success_response(
        {"costEntry": entry},
        "批次成本已登记" if created else "该批次成本已登记",
        201 if created else 200,
    )


@livestock_bp.post("/livestock-cost-entries/<int:entry_id>/cancel")
@login_required
def cancel_livestock_cost_entry_record(entry_id):
    return success_response(
        {"costEntry": cancel_livestock_cost_entry(entry_id, g.current_user)},
        "批次成本已撤销",
    )
