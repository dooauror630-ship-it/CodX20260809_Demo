from flask import Blueprint, g, request

from ...core.errors import success_response
from ...core.security import admin_required, login_required
from ..auth.schemas import parse_payload
from .schemas import (
    CreateBarnPayload,
    CreateFarmMemberPayload,
    CreateFarmPayload,
    CreatePlotPayload,
    FarmListQuery,
    FarmResourceListQuery,
    UpdateBarnPayload,
    UpdateFarmMemberPayload,
    UpdateFarmPayload,
    UpdatePlotPayload,
)
from .service import (
    add_farm_member,
    create_barn,
    create_farm,
    create_plot,
    farm_payload,
    get_accessible_farm,
    list_barns,
    list_farm_members,
    list_farms,
    list_plots,
    update_barn,
    update_farm,
    update_farm_member,
    update_plot,
)


farm_bp = Blueprint("farm", __name__)


@farm_bp.get("/farms")
@login_required
def farms():
    query = parse_payload(FarmListQuery, request.args.to_dict(), "筛选条件格式错误")
    return success_response(list_farms(query, g.current_user))


@farm_bp.get("/farms/<int:farm_id>")
@login_required
def farm_detail(farm_id):
    farm, role = get_accessible_farm(farm_id, g.current_user)
    return success_response({"farm": farm_payload(farm, access_role=role)})


@farm_bp.post("/farms")
@admin_required
def add_farm():
    payload = parse_payload(CreateFarmPayload, request.get_json(silent=True), "农场信息格式错误")
    return success_response({"farm": create_farm(payload, g.current_user)}, "农场已创建", 201)


@farm_bp.patch("/farms/<int:farm_id>")
@admin_required
def edit_farm(farm_id):
    payload = parse_payload(UpdateFarmPayload, request.get_json(silent=True), "农场信息格式错误")
    return success_response({"farm": update_farm(farm_id, payload, g.current_user)}, "农场信息已更新")


@farm_bp.get("/farms/<int:farm_id>/members")
@admin_required
def farm_members(farm_id):
    return success_response({"items": list_farm_members(farm_id)})


@farm_bp.post("/farms/<int:farm_id>/members")
@admin_required
def add_member(farm_id):
    payload = parse_payload(CreateFarmMemberPayload, request.get_json(silent=True), "成员信息格式错误")
    return success_response({"member": add_farm_member(farm_id, payload)}, "农场成员已保存", 201)


@farm_bp.patch("/farms/<int:farm_id>/members/<int:user_id>")
@admin_required
def edit_member(farm_id, user_id):
    payload = parse_payload(UpdateFarmMemberPayload, request.get_json(silent=True), "成员信息格式错误")
    return success_response({"member": update_farm_member(farm_id, user_id, payload)}, "成员权限已更新")


@farm_bp.get("/barns")
@login_required
def barns():
    query = parse_payload(FarmResourceListQuery, request.args.to_dict(), "筛选条件格式错误")
    return success_response(list_barns(query, g.current_user))


@farm_bp.post("/barns")
@admin_required
def add_barn():
    payload = parse_payload(CreateBarnPayload, request.get_json(silent=True), "圈舍信息格式错误")
    return success_response({"barn": create_barn(payload, g.current_user)}, "圈舍已创建", 201)


@farm_bp.patch("/barns/<int:barn_id>")
@admin_required
def edit_barn(barn_id):
    payload = parse_payload(UpdateBarnPayload, request.get_json(silent=True), "圈舍信息格式错误")
    return success_response({"barn": update_barn(barn_id, payload, g.current_user)}, "圈舍信息已更新")


@farm_bp.get("/plots")
@login_required
def plots():
    query = parse_payload(FarmResourceListQuery, request.args.to_dict(), "筛选条件格式错误")
    return success_response(list_plots(query, g.current_user))


@farm_bp.post("/plots")
@admin_required
def add_plot():
    payload = parse_payload(CreatePlotPayload, request.get_json(silent=True), "地块信息格式错误")
    return success_response({"plot": create_plot(payload, g.current_user)}, "地块已创建", 201)


@farm_bp.patch("/plots/<int:plot_id>")
@admin_required
def edit_plot(plot_id):
    payload = parse_payload(UpdatePlotPayload, request.get_json(silent=True), "地块信息格式错误")
    return success_response({"plot": update_plot(plot_id, payload, g.current_user)}, "地块信息已更新")
