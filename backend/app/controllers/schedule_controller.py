"""일정 조회/등록 API. 입력 전달과 응답만 처리합니다."""

from flask import Blueprint, g, jsonify, request
from app.services import schedule_service

blueprint = Blueprint("schedules", __name__)


@blueprint.get("/api/schedules")
def schedules():
    return jsonify(schedule_service.schedules(request.args, g.user))


@blueprint.get("/api/schedules/<int:schedule_id>")
def schedule_detail(schedule_id):
    return jsonify(schedule_service.schedule_detail(schedule_id))


@blueprint.post("/api/schedules")
def create_schedule():
    return jsonify(schedule_service.create_schedule(request.get_json(), g.user)), 201


@blueprint.put('/api/schedules/<int:schedule_id>')
def update_schedule(schedule_id):
    return jsonify(schedule_service.update_schedule(schedule_id, request.get_json(), g.user))


@blueprint.delete('/api/schedules/<int:schedule_id>')
def delete_schedule(schedule_id):
    return jsonify(schedule_service.delete_schedule(schedule_id, g.user))


@blueprint.get('/api/schedules/notifications')
def notifications():
    return jsonify(schedule_service.schedule_notifications(g.user))


@blueprint.post('/api/schedules/notifications/read')
def read_notifications():
    return jsonify(schedule_service.read_schedule_notifications(request.get_json(), g.user))
