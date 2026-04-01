import logging
import os
import traceback
from logging.handlers import RotatingFileHandler

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

load_dotenv()


def _configure_logging(flask_app):
    if getattr(_configure_logging, "_configured", False):
        return

    log_file = os.getenv("LOG_FILE", "./logs/app.log")
    log_level = os.getenv("LOG_LEVEL", "INFO")
    level = getattr(logging, log_level.upper(), logging.INFO)

    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(process)d - %(thread)d - %(message)s"
    )

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    root_logger.setLevel(level)

    # Avoid duplicate records from the `app.*` logger tree by routing Flask logs
    # through the configured root handlers only.
    flask_app.logger.handlers.clear()
    flask_app.logger.setLevel(level)
    flask_app.logger.propagate = True

    _configure_logging._configured = True


def _register_error_handlers(flask_app):
    @flask_app.errorhandler(404)
    def not_found_error(error):
        flask_app.logger.error("404 Error: %s", request.path)
        return jsonify({"error": "Resource not found"}), 404

    @flask_app.errorhandler(500)
    def internal_error(error):
        flask_app.logger.error("500 Error: %s", traceback.format_exc())
        return jsonify({"error": "Internal server error"}), 500

    @flask_app.errorhandler(Exception)
    def general_error(error):
        flask_app.logger.error("General Error: %s", traceback.format_exc())
        return jsonify({"error": "An unexpected error occurred"}), 500


def _register_core_routes(flask_app):
    @flask_app.route("/health", methods=["GET"])
    def health_check():
        return jsonify({"status": "ok", "message": "Service is running"}), 200

    @flask_app.route("/", methods=["GET"])
    def index():
        return jsonify({"message": "Welcome to Douyin Live Recorder API"}), 200


def create_app():
    flask_app = Flask(__name__)
    flask_app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "default_secret_key")
    flask_app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL", "sqlite:///./data.db"
    )
    flask_app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    CORS(flask_app)
    _configure_logging(flask_app)

    from app.models import db
    from app.services.anchor_sync_service import anchor_sync_service

    db.init_app(flask_app)

    with flask_app.app_context():
        db.create_all()
        anchor_sync_service.sync()

    _register_error_handlers(flask_app)
    _register_core_routes(flask_app)

    from app.api import routes

    flask_app.register_blueprint(routes.bp)
    return flask_app


app = create_app()
