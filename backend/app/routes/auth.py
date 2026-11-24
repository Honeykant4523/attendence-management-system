import hashlib
import secrets
from datetime import datetime, timedelta

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import create_access_token, jwt_required

from ..extensions import db
from ..models import Employee, PasswordResetToken, Role, User, add_audit_log
from ..utils.security import current_user, roles_required
from ..utils.validation import payload

auth_bp = Blueprint("auth", __name__)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@auth_bp.post("/auth/register")
def register():
    data, error = payload(("email", "password", "firstName", "lastName"))
    if error:
        return error
    if len(data["password"]) < 10:
        return jsonify({"error": "Password must be at least 10 characters."}), 400
    if User.query.filter_by(email=data["email"].strip().lower()).first():
        return jsonify({"error": "An account with this email already exists."}), 409
    # Only the very first account can become the bootstrap administrator.
    requested_role = data.get("role", Role.EMPLOYEE.value)
    if User.query.count() == 0:
        requested_role = Role.SUPER_ADMIN.value
    else:
        from flask_jwt_extended import verify_jwt_in_request
        try:
            verify_jwt_in_request()
            actor = current_user()
        except Exception:
            actor = None
        if not actor or actor.role != Role.SUPER_ADMIN.value:
            return jsonify({"error": "Only a super admin can create additional accounts."}), 403
        if requested_role not in {role.value for role in Role}:
            return jsonify({"error": "Invalid role."}), 400

    user = User(email=data["email"].strip().lower(), role=requested_role)
    user.set_password(data["password"])
    db.session.add(user)
    db.session.flush()
    employee = Employee(user_id=user.id, employee_code=data.get("employeeCode") or f"EMP-{user.id:05d}",
                        first_name=data["firstName"].strip(), last_name=data["lastName"].strip(),
                        phone=data.get("phone"), department_id=data.get("departmentId"),
                        designation_id=data.get("designationId"), shift_id=data.get("shiftId"))
    db.session.add(employee)
    add_audit_log(user.id, "account_created", "user", user.id, {"role": user.role}, request.remote_addr)
    db.session.commit()
    return jsonify({"user": user.to_dict(), "employee": employee.to_dict()}), 201


@auth_bp.post("/auth/login")
def login():
    data, error = payload(("email", "password"))
    if error:
        return error
    user = User.query.filter_by(email=data["email"].strip().lower()).first()
    if not user or not user.is_active or not user.check_password(data["password"]):
        return jsonify({"error": "Invalid email or password."}), 401
    token = create_access_token(identity=str(user.id), additional_claims={"role": user.role})
    add_audit_log(user.id, "login", "user", user.id, ip_address=request.remote_addr)
    db.session.commit()
    return jsonify({"accessToken": token, "user": user.to_dict(), "employee": user.employee.to_dict()})


@auth_bp.get("/auth/me")
@jwt_required()
def me():
    user = current_user()
    if not user or not user.is_active:
        return jsonify({"error": "Account is unavailable."}), 403
    return jsonify({"user": user.to_dict(), "employee": user.employee.to_dict() if user.employee else None})


@auth_bp.post("/auth/forgot-password")
def forgot_password():
    data, error = payload(("email",))
    if error:
        return error
    user = User.query.filter_by(email=data["email"].strip().lower()).first()
    response = {"message": "If the account exists, reset instructions have been created."}
    if user:
        raw_token = secrets.token_urlsafe(32)
        db.session.add(PasswordResetToken(user_id=user.id, token_hash=_token_hash(raw_token),
                                          expires_at=datetime.utcnow() + timedelta(minutes=30)))
        db.session.commit()
        # Production must deliver this through a configured email provider, never API response.
        if current_app.debug:
            response["developmentResetToken"] = raw_token
    return jsonify(response)


@auth_bp.post("/auth/reset-password")
def reset_password():
    data, error = payload(("token", "newPassword"))
    if error:
        return error
    if len(data["newPassword"]) < 10:
        return jsonify({"error": "Password must be at least 10 characters."}), 400
    reset = PasswordResetToken.query.filter_by(token_hash=_token_hash(data["token"]), used_at=None).first()
    if not reset or reset.expires_at < datetime.utcnow():
        return jsonify({"error": "This reset token is invalid or expired."}), 400
    user = User.query.get(reset.user_id)
    user.set_password(data["newPassword"])
    reset.used_at = datetime.utcnow()
    add_audit_log(user.id, "password_reset", "user", user.id, ip_address=request.remote_addr)
    db.session.commit()
    return jsonify({"message": "Password updated. You can now sign in."})
