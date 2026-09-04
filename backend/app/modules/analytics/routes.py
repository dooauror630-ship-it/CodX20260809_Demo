from flask import Blueprint, g, request

from ...core.errors import success_response
from ...core.security import admin_required, login_required
from .service import system_overview, farm_overview


analytics_bp = Blueprint("analytics", __name__)


@analytics_bp.get("/overview")
@admin_required
def overview():
    return success_response(system_overview())


@analytics_bp.get("/farm-overview")
@login_required
def farm_overview_route():
    return success_response(farm_overview(request.args.get("farmId", type=int), g.current_user))
