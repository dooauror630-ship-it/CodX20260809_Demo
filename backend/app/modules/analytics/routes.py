from flask import Blueprint

from ...core.errors import success_response
from ...core.security import admin_required
from .service import system_overview


analytics_bp = Blueprint("analytics", __name__)


@analytics_bp.get("/overview")
@admin_required
def overview():
    return success_response(system_overview())
