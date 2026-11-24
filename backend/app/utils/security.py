from functools import wraps

from flask import jsonify
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from ..extensions import db
from ..models import Employee, Role, User


def current_user():
    user_id = get_jwt_identity()
    return db.session.get(User, int(user_id)) if user_id else None


def current_employee():
    user = current_user()
    return user.employee if user else None


def roles_required(*allowed_roles):
    """Protect a route and enforce one or more explicit application roles."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            user = current_user()
            if not user or not user.is_active:
                return jsonify({"error": "Your account is unavailable."}), 403
            if user.role not in allowed_roles:
                return jsonify({"error": "You do not have permission for this action."}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def can_access_employee(target_employee_id: int) -> bool:
    user = current_user()
    return bool(user and (user.role in (Role.SUPER_ADMIN.value, Role.HR_ADMIN.value) or
                          (user.employee and user.employee.id == target_employee_id)))
