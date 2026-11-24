from .attendance import attendance_bp
from .auth import auth_bp
from .chatbot import chatbot_bp
from .dashboard import dashboard_bp
from .employees import employees_bp
from .leaves import leaves_bp
from .reports import reports_bp


def register_blueprints(app):
    for blueprint in (auth_bp, dashboard_bp, employees_bp, attendance_bp, leaves_bp, reports_bp, chatbot_bp):
        app.register_blueprint(blueprint, url_prefix="/api")
