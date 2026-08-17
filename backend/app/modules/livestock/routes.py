from flask import Blueprint, g, request

from ...core.errors import success_response
from ...core.security import login_required
from ..auth.schemas import parse_payload
from .schemas import CreateLivestockBatchPayload, CreateLivestockMovementPayload, LivestockBatchListQuery
from .service import create_livestock_batch, create_livestock_movement, livestock_batch_detail, list_livestock_batches


livestock_bp = Blueprint("livestock", __name__)


@livestock_bp.get("/livestock-batches")
@login_required
def livestock_batches():
    query = parse_payload(LivestockBatchListQuery, request.args.to_dict(), "养殖批次筛选条件格式错误")
    return success_response(list_livestock_batches(query, g.current_user))


@livestock_bp.get("/livestock-batches/<int:batch_id>")
@login_required
def livestock_batch(batch_id):
    return success_response({"batch": livestock_batch_detail(batch_id, g.current_user)})


@livestock_bp.post("/livestock-batches")
@login_required
def add_livestock_batch():
    payload = parse_payload(CreateLivestockBatchPayload, request.get_json(silent=True), "生猪批次入栏信息格式错误")
    batch, created = create_livestock_batch(payload, g.current_user)
    return success_response(
        {"batch": batch},
        "生猪批次已入栏" if created else "该生猪批次已入栏",
        201 if created else 200,
    )


@livestock_bp.post("/livestock-movements")
@login_required
def add_livestock_movement():
    payload = parse_payload(CreateLivestockMovementPayload, request.get_json(silent=True), "生猪存栏变动信息格式错误")
    movement, batch, created = create_livestock_movement(payload, g.current_user)
    return success_response(
        {"movement": movement, "batch": batch},
        "存栏变动已登记" if created else "该存栏变动已登记",
        201 if created else 200,
    )
