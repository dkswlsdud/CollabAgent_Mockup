"""API 인증, 오류 응답, 공통 응답 헤더."""

import pymysql
from flask import current_app, g, jsonify, request
from werkzeug.exceptions import HTTPException
from app.shared.errors import AppError, fail
from app.config import COOKIE
from app.services import auth_service


def register_middleware(app):
    @app.before_request
    def authenticate():
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("Origin")
            if origin and origin != request.host_url.rstrip("/"):
                fail("허용하지 않는 요청 출처입니다.", 403)
            multipart=request.path=='/api/requests' and request.mimetype=='multipart/form-data'
            if request.is_json and (request.content_length or 0)>128*1024:fail('요청 내용이 너무 큽니다.',413)
            if not request.is_json and not multipart:
                fail("JSON 요청이 필요합니다.", 415)
            if not multipart and not isinstance(request.get_json(), dict):
                fail('JSON 객체를 전달해주세요.')
        if request.path in {"/api/health", "/api/auth/login"}:
            return
        token = request.cookies.get(COOKIE, "")
        if not token:
            fail("로그인이 필요합니다.", 401)
        g.user = auth_service.session_user(token)
        if not g.user:
            fail("로그인이 만료되었습니다.", 401)

    @app.errorhandler(AppError)
    def business_error(error):
        return jsonify(error=error.message), error.status

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error=error.description), error.code

    @app.errorhandler(pymysql.MySQLError)
    def database_error(error):
        code = error.args[0] if error.args else None
        current_app.logger.warning("Database operation failed (code=%s)", code)
        if isinstance(error, pymysql.IntegrityError):
            return (
                jsonify(
                    error="중복되거나 연결할 수 없는 데이터입니다. 입력값을 확인해주세요."
                ),
                409,
            )
        return (
            jsonify(
                error="DB 연결 또는 테이블을 확인해주세요. .env 설정 후 DB 초기화가 필요합니다."
            ),
            503,
        )

    @app.after_request
    def response_headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response
