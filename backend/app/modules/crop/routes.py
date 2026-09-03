from flask import Blueprint, g, request

from ...core.errors import success_response
from ...core.security import login_required
from ..auth.schemas import parse_payload
from .schemas import (
    CropCycleListQuery,
    CreateCropCyclePayload,
    CreateFieldOperationPayload,
    CreateFieldOperationInputPayload,
    FieldOperationInputListQuery,
    FieldOperationListQuery,
    UpdateCropCycleStatusPayload,
    CreateHarvestBatchPayload, HarvestBatchListQuery,
    CompleteTobaccoCuringBatchPayload, CreateTobaccoCuringBatchPayload, TobaccoCuringBatchListQuery,
    CreateGradingRecordPayload, GradingRecordListQuery,
)
from .service import (
    create_crop_cycle,
    create_field_operation,
    create_field_operation_input,
    get_crop_cycle,
    crop_cycle_analysis,
    crop_cycle_cost_summary,
    list_crop_cycles,
    list_field_operations,
    list_available_field_operation_inputs,
    list_field_operation_inputs,
    update_crop_cycle_status,
    create_harvest_batch, list_harvest_batches,
    complete_tobacco_curing_batch, create_tobacco_curing_batch, list_tobacco_curing_batches,
    create_grading_record, list_grading_records,
)


crop_bp = Blueprint("crop", __name__)


@crop_bp.get("/crop-cycles")
@login_required
def crop_cycles():
    query = parse_payload(CropCycleListQuery, request.args.to_dict(), "种植周期筛选条件格式错误")
    return success_response(list_crop_cycles(query, g.current_user))


@crop_bp.get("/crop-cycles/<int:cycle_id>")
@login_required
def crop_cycle_detail(cycle_id):
    return success_response({"cycle": get_crop_cycle(cycle_id, g.current_user)})


@crop_bp.get("/crop-cycles/<int:cycle_id>/cost-summary")
@login_required
def crop_cycle_cost(cycle_id):
    return success_response(crop_cycle_cost_summary(cycle_id, g.current_user))


@crop_bp.get("/crop-cycles/<int:cycle_id>/analysis")
@login_required
def crop_cycle_analysis_overview(cycle_id):
    return success_response(crop_cycle_analysis(cycle_id, g.current_user))


@crop_bp.post("/crop-cycles")
@login_required
def add_crop_cycle():
    payload = parse_payload(CreateCropCyclePayload, request.get_json(silent=True), "种植周期信息格式错误")
    cycle, created = create_crop_cycle(payload, g.current_user)
    return success_response(
        {"cycle": cycle}, "种植周期已创建" if created else "该种植周期已创建", 201 if created else 200
    )


@crop_bp.patch("/crop-cycles/<int:cycle_id>/status")
@login_required
def edit_crop_cycle_status(cycle_id):
    payload = parse_payload(UpdateCropCycleStatusPayload, request.get_json(silent=True), "种植周期状态格式错误")
    return success_response(
        {"cycle": update_crop_cycle_status(cycle_id, payload, g.current_user)}, "种植周期状态已更新"
    )


@crop_bp.get("/field-operations")
@login_required
def field_operations():
    query = parse_payload(FieldOperationListQuery, request.args.to_dict(), "农事操作筛选条件格式错误")
    return success_response(list_field_operations(query, g.current_user))


@crop_bp.post("/field-operations")
@login_required
def add_field_operation():
    payload = parse_payload(CreateFieldOperationPayload, request.get_json(silent=True), "农事操作信息格式错误")
    return success_response({"operation": create_field_operation(payload, g.current_user)}, "农事操作已登记", 201)


@crop_bp.get("/field-operation-inputs")
@login_required
def field_operation_inputs():
    query = parse_payload(FieldOperationInputListQuery, request.args.to_dict(), "农事投入品筛选条件格式错误")
    return success_response(list_field_operation_inputs(query, g.current_user))


@crop_bp.get("/field-operation-inputs/available")
@login_required
def available_field_operation_inputs():
    query = parse_payload(FieldOperationInputListQuery, request.args.to_dict(), "可用农事投入品筛选条件格式错误")
    return success_response(list_available_field_operation_inputs(query, g.current_user))


@crop_bp.post("/field-operation-inputs")
@login_required
def add_field_operation_input():
    payload = parse_payload(CreateFieldOperationInputPayload, request.get_json(silent=True), "农事投入品信息格式错误")
    input_record, created = create_field_operation_input(payload, g.current_user)
    return success_response(
        {"input": input_record},
        "农事投入品已绑定" if created else "该库存领料单已绑定",
        201 if created else 200,
    )


@crop_bp.get("/harvest-batches")
@login_required
def harvest_batches():
    query = parse_payload(HarvestBatchListQuery, request.args.to_dict(), "采收批次筛选条件格式错误")
    return success_response(list_harvest_batches(query, g.current_user))


@crop_bp.post("/harvest-batches")
@login_required
def add_harvest_batch():
    payload = parse_payload(CreateHarvestBatchPayload, request.get_json(silent=True), "采收批次信息格式错误")
    batch, created = create_harvest_batch(payload, g.current_user)
    return success_response({"batch": batch}, "采收批次已登记" if created else "该采收批次已登记", 201 if created else 200)


@crop_bp.get("/tobacco-curing-batches")
@login_required
def tobacco_curing_batches():
    query = parse_payload(TobaccoCuringBatchListQuery, request.args.to_dict(), "烘烤批次筛选条件格式错误")
    return success_response(list_tobacco_curing_batches(query, g.current_user))


@crop_bp.post("/tobacco-curing-batches")
@login_required
def add_tobacco_curing_batch():
    payload = parse_payload(CreateTobaccoCuringBatchPayload, request.get_json(silent=True), "烘烤批次信息格式错误")
    batch, created = create_tobacco_curing_batch(payload, g.current_user)
    return success_response({"batch": batch}, "烘烤批次已开始" if created else "该烘烤批次已开始", 201 if created else 200)


@crop_bp.patch("/tobacco-curing-batches/<int:batch_id>/complete")
@login_required
def complete_curing_batch(batch_id):
    payload = parse_payload(CompleteTobaccoCuringBatchPayload, request.get_json(silent=True), "烘烤完成信息格式错误")
    return success_response({"batch": complete_tobacco_curing_batch(batch_id, payload, g.current_user)}, "烘烤批次已完成")


@crop_bp.get("/grading-records")
@login_required
def grading_records():
    query = parse_payload(GradingRecordListQuery, request.args.to_dict(), "分级记录筛选条件格式错误")
    return success_response(list_grading_records(query, g.current_user))


@crop_bp.post("/grading-records")
@login_required
def add_grading_record():
    payload = parse_payload(CreateGradingRecordPayload, request.get_json(silent=True), "分级记录信息格式错误")
    record, created = create_grading_record(payload, g.current_user)
    return success_response({"record": record}, "分级记录已登记" if created else "该等级已登记", 201 if created else 200)
