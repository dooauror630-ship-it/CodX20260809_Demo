from flask import Blueprint, current_app, g, jsonify
from sqlalchemy import text

from ...extensions import db


system_bp = Blueprint("system", __name__)


def health_response():
    db.session.execute(text("SELECT 1"))
    return jsonify({
        "success": True,
        "service": "agriculture-management",
        "database": current_app.config["DATABASE_ENGINE"],
        "requestId": g.request_id,
    })


@system_bp.get("/api/health")
def health():
    return health_response()


@system_bp.get("/api/v1/system/health")
def versioned_health():
    return health_response()
