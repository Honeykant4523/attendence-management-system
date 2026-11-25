from pathlib import Path

from flask import Flask, jsonify
from flask_cors import CORS
from sqlalchemy import text

from config import Config
from .extensions import bcrypt, db, jwt


def _upgrade_sqlite_corrections_table():
    """Upgrade the early local SQLite schema where attendance_id was required.

    Pending manual check-in requests do not yet have an attendance record, so their
    attendance_id must be nullable. Production databases should use migrations.
    """
    if db.engine.dialect.name != "sqlite":
        return
    with db.engine.begin() as connection:
        columns = connection.execute(text("PRAGMA table_info(attendance_corrections)")).mappings().all()
        attendance_id = next((column for column in columns if column["name"] == "attendance_id"), None)
        if not attendance_id or not attendance_id["notnull"]:
            return
        connection.execute(text("""
            CREATE TABLE attendance_corrections_new (
                id INTEGER NOT NULL PRIMARY KEY,
                attendance_id INTEGER,
                requested_by_id INTEGER NOT NULL,
                reason VARCHAR(1000) NOT NULL,
                requested_check_in DATETIME,
                requested_check_out DATETIME,
                status VARCHAR(20) NOT NULL,
                reviewed_by_id INTEGER,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                FOREIGN KEY(attendance_id) REFERENCES attendance (id) ON DELETE CASCADE,
                FOREIGN KEY(requested_by_id) REFERENCES users (id) ON DELETE CASCADE,
                FOREIGN KEY(reviewed_by_id) REFERENCES users (id) ON DELETE SET NULL
            )
        """))
        connection.execute(text("""
            INSERT INTO attendance_corrections_new
              (id, attendance_id, requested_by_id, reason, requested_check_in,
               requested_check_out, status, reviewed_by_id, created_at, updated_at)
            SELECT id, attendance_id, requested_by_id, reason, requested_check_in,
                   requested_check_out, status, reviewed_by_id, created_at, updated_at
            FROM attendance_corrections
        """))
        connection.execute(text("DROP TABLE attendance_corrections"))
        connection.execute(text("ALTER TABLE attendance_corrections_new RENAME TO attendance_corrections"))


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
        _upgrade_sqlite_corrections_table()

    return app
