"""협업 요청 및 협상 동작 API."""

import json
from io import BytesIO
from flask import Blueprint, g, jsonify, request, send_file
from app.shared.errors import fail
from app.services import attachment_service
from app.services import request_service, negotiation_service, intake_service

blueprint = Blueprint("requests", __name__)


@blueprint.post('/api/requests/analyze')
def analyze_request():
    return jsonify(intake_service.analyze(request.get_json(), g.user))


@blueprint.get("/api/requests")
def requests_list():
    return jsonify(request_service.requests_list(g.user))


@blueprint.get("/api/requests/<int:request_id>")
def request_detail(request_id):
    return jsonify(request_service.request_detail(request_id, g.user))


@blueprint.post("/api/requests")
def create_request():
    if request.is_json:data=request.get_json()
    else:
        try:data=json.loads(request.form.get('payload',''))
        except (ValueError,TypeError):fail('요청 내용을 확인해주세요.')
        if not isinstance(data,dict):fail('요청 내용을 확인해주세요.')
    return jsonify(request_service.create_request(data,g.user,list(request.files.getlist('attachments')))),201


@blueprint.post("/api/requests/<int:request_id>/action")
def request_action(request_id):
    return jsonify(
        negotiation_service.request_action(request_id, request.get_json(), g.user)
    )


@blueprint.post('/api/requests/<int:request_id>/read')
def read_request(request_id):
    return jsonify(request_service.acknowledge_request(request_id,request.get_json(),g.user))


@blueprint.get('/api/attachments/<int:attachment_id>')
def download_attachment(attachment_id):
    row=attachment_service.download(attachment_id,g.user)
    return send_file(BytesIO(row['content']),mimetype='application/octet-stream',as_attachment=True,download_name=row['filename'])
