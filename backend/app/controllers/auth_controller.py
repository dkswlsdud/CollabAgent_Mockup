"""직원 로그인, 세션, 상태 확인 API."""

from flask import Blueprint, g, jsonify, request
from app.config import COOKIE
from app.services import auth_service

blueprint = Blueprint("auth", __name__)


@blueprint.get("/api/health")
def health():
    return jsonify(auth_service.health())


@blueprint.post("/api/auth/login")
def login():
    user, token = auth_service.login(request.get_json())
    response = jsonify(user=user)
    response.set_cookie(
        COOKIE,
        token,
        max_age=604800,
        httponly=True,
        samesite="Lax",
        secure=False,
        path="/",
    )
    return response


@blueprint.get("/api/auth/me")
def me():
    return jsonify(user=g.user)


@blueprint.post("/api/auth/logout")
def logout():
    response = jsonify(auth_service.logout(request.cookies.get(COOKIE, "")))
    response.delete_cookie(COOKIE, path="/")
    return response
