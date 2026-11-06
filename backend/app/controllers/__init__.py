"""도메인별 컨트롤러 등록."""

from app.controllers import (
    auth_controller,
    employee_controller,
    schedule_controller,
    request_controller,
    consent_controller,
)


def register_controllers(app):
    for controller in (
        auth_controller,
        employee_controller,
        schedule_controller,
        request_controller,
        consent_controller,
    ):
        app.register_blueprint(controller.blueprint)
