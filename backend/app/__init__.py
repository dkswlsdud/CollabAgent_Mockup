"""Flask application factory."""
from flask import Flask
from app.controllers import register_controllers
from app.middleware import register_middleware


def create_app():
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024
    register_middleware(app)
    register_controllers(app)
    return app
