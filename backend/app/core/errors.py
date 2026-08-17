from flask import current_app, g, jsonify, request
from werkzeug.exceptions import HTTPException

from ..extensions import db


class ApiError(Exception):
    def __init__(self, message, status=400, code="REQUEST_INVALID", field=None, details=None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code
        self.field = field
        self.details = details


def success_response(data=None, message=None, status=200):
    body = {"success": True, "requestId": getattr(g, "request_id", None)}
    if data is not None:
        body["data"] = data
    if message:
        body["message"] = message
    return jsonify(body), status


def error_response(error):
    body = {
        "success": False,
        "code": error.code,
        "message": error.message,
        "requestId": getattr(g, "request_id", None),
    }
    if error.field:
        body["field"] = error.field
    if error.details is not None:
        body["details"] = error.details
    return jsonify(body), error.status


def register_error_handlers(app):
    @app.errorhandler(ApiError)
    def handle_api_error(error):
        db.session.rollback()
        return error_response(error)

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        if not request.path.startswith("/api/"):
            return error
        return error_response(ApiError(error.description, error.code, f"HTTP_{error.code}"))

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        db.session.rollback()
        current_app.logger.exception(
            "Unhandled request error request_id=%s",
            getattr(g, "request_id", None),
        )
        if current_app.testing:
            raise error
        return error_response(ApiError("服务器内部错误", 500, "INTERNAL_ERROR"))
