"""직원 조회 API."""

from flask import Blueprint, jsonify
from app.services import employee_service

blueprint = Blueprint("employees", __name__)


@blueprint.get("/api/employees")
def employees():
    return jsonify(employee_service.employees())
