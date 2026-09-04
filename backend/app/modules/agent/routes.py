import secrets
from functools import wraps

from flask import Blueprint, current_app, request

from ...core.errors import ApiError, success_response
from .service import inventory_summary, list_farms, livestock_summary


agent_bp = Blueprint("agent", __name__)


def agent_api_key_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        expected = current_app.config.get("AGENT_API_KEY", "")
        supplied = request.headers.get("x-api-key", "")
        if supplied.startswith("Bearer "):
            supplied = supplied[7:]
        if not expected:
            raise ApiError("智能体接口尚未配置 API Key", 503, "AGENT_API_KEY_NOT_CONFIGURED")
        if not supplied or not secrets.compare_digest(supplied, expected):
            raise ApiError("API Key 无效或缺失", 401, "AGENT_API_KEY_INVALID")
        return view(*args, **kwargs)

    return wrapped


def _farm_id():
    farm_id = request.args.get("farmId", type=int)
    if farm_id is None or farm_id <= 0:
        raise ApiError("farmId 必须是正整数", 400, "FARM_ID_INVALID", "farmId")
    return farm_id


@agent_bp.get("/farms")
@agent_api_key_required
def farms():
    return success_response(list_farms())


@agent_bp.get("/inventory-summary")
@agent_api_key_required
def inventory():
    return success_response(inventory_summary(_farm_id()))


@agent_bp.get("/livestock-summary")
@agent_api_key_required
def livestock():
    return success_response(livestock_summary(_farm_id()))
