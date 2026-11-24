from pathlib import Path

from flask import Flask, jsonify
from flask_cors import CORS

from config import Config
from .extensions import bcrypt, db, jwt


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    bcrypt.init_app(app)
    jwt.init_app(app)
    CORS(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})

    from .routes import register_blueprints
    register_blueprints(app)

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "service": "SmartAttend API"})

    @app.errorhandler(413)
    def file_too_large(_error):
        return jsonify({"error": "Uploaded file exceeds the 8 MB limit."}), 413

    with app.app_context():
        from . import models  # noqa: F401 - register models before create_all
        db.create_all()

    return app
