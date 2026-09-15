import csv
from io import StringIO
from flask import Blueprint, g, request, Response

from ...core.errors import success_response
from ...core.security import admin_required, login_required
from .service import system_overview, farm_overview
from ..trade.service import trade_profit


analytics_bp = Blueprint("analytics", __name__)


@analytics_bp.get("/overview")
@admin_required
def overview():
    return success_response(system_overview())


@analytics_bp.get("/farm-overview")
@login_required
def farm_overview_route():
    return success_response(farm_overview(request.args.get("farmId", type=int), g.current_user))


@analytics_bp.get("/trade-profit.csv")
@login_required
def trade_profit_export():
    rows = trade_profit(request.args.get("farmId", type=int), g.current_user)
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["orderNo", "saleDate", "revenue", "cost", "grossProfit", "receivedAmount"])
    for row in rows:
        writer.writerow([row[key] for key in ("orderNo", "saleDate", "revenue", "cost", "grossProfit", "receivedAmount")])
    return Response("\ufeff" + output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=trade-profit.csv"})
