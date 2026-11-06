"""관계자 동의 조회/응답 API."""

from flask import Blueprint, g, jsonify, request
from app.services import consent_service

blueprint = Blueprint("consents", __name__)


@blueprint.get("/api/consents")
def my_consents():
    return jsonify(consent_service.my_consents(g.user))


@blueprint.get('/api/consents/<consent_id>')
def consent_detail(consent_id):
    return jsonify(consent_service.consent_detail(consent_id, g.user))


@blueprint.post("/api/consents/<consent_id>")
def answer_consent(consent_id):
    return jsonify(
        consent_service.answer_consent(consent_id, request.get_json(), g.user)
    )


@blueprint.post('/api/consents/<consent_id>/calendar-settings')
def calendar_settings(consent_id):
    return jsonify(consent_service.consent_calendar_settings(consent_id,request.get_json(),g.user))


@blueprint.post('/api/consents/<consent_id>/read')
def read_consent(consent_id):
    return jsonify(consent_service.acknowledge_consent(consent_id,request.get_json(),g.user))
