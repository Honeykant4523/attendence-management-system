from datetime import datetime, time

from flask import Blueprint, jsonify, request
from sqlalchemy import or_

from ..extensions import db
from ..models import Department, Designation, Employee, Holiday, FaceTemplate, Role, Shift, User, add_audit_log
from ..utils.security import can_access_employee, current_employee, current_user, roles_required
from ..utils.validation import payload

employees_bp = Blueprint("employees", __name__)


@employees_bp.get("/employees")
@roles_required(Role.SUPER_ADMIN.value, Role.HR_ADMIN.value)
def list_employees():
    page = max(1, request.args.get("page", 1, type=int))
    per_page = min(100, max(1, request.args.get("perPage", 20, type=int)))
    query = Employee.query
    search = request.args.get("search", "").strip()
    if search:
        wildcard = f"%{search}%"
        query = query.join(User).filter(or_(Employee.first_name.ilike(wildcard), Employee.last_name.ilike(wildcard),
                                             Employee.employee_code.ilike(wildcard), User.email.ilike(wildcard)))
    if request.args.get("departmentId", type=int):
        query = query.filter(Employee.department_id == request.args.get("departmentId", type=int))
    pagination = query.order_by(Employee.first_name, Employee.last_name).paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({"items": [employee.to_dict() for employee in pagination.items],
                    "pagination": {"page": page, "perPage": per_page, "total": pagination.total, "pages": pagination.pages}})


@employees_bp.get("/employees/<int:employee_id>")
@roles_required(Role.SUPER_ADMIN.value, Role.HR_ADMIN.value, Role.EMPLOYEE.value)
def get_employee(employee_id):
    if not can_access_employee(employee_id):
        return jsonify({"error": "You may only access your own profile."}), 403
    employee = db.session.get(Employee, employee_id)
    if not employee:
        return jsonify({"error": "Employee not found."}), 404
    return jsonify({"employee": employee.to_dict()})


@employees_bp.post("/employees")
@roles_required(Role.SUPER_ADMIN.value, Role.HR_ADMIN.value)
def create_employee():
    data, error = payload(("email", "password", "firstName", "lastName"))
    if error:
        return error
    email = data["email"].strip().lower()
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already exists."}), 409
    if len(data["password"]) < 10:
        return jsonify({"error": "Temporary password must be at least 10 characters."}), 400
    actor = current_user()
    role = data.get("role", Role.EMPLOYEE.value)
    if role == Role.SUPER_ADMIN.value and actor.role != Role.SUPER_ADMIN.value:
        return jsonify({"error": "Only super admins can create super admins."}), 403
    if role not in {item.value for item in Role}:
        return jsonify({"error": "Invalid role."}), 400
    user = User(email=email, role=role)
    user.set_password(data["password"])
    db.session.add(user)
    db.session.flush()
    employee = Employee(user_id=user.id, employee_code=data.get("employeeCode") or f"EMP-{user.id:05d}",
                        first_name=data["firstName"].strip(), last_name=data["lastName"].strip(),
                        phone=data.get("phone"), department_id=data.get("departmentId"),
                        designation_id=data.get("designationId"), shift_id=data.get("shiftId"))
    db.session.add(employee)
    add_audit_log(actor.id, "employee_created", "employee", employee.employee_code, {"email": email}, request.remote_addr)
    db.session.commit()
    return jsonify({"employee": employee.to_dict()}), 201


@employees_bp.patch("/employees/<int:employee_id>")
@roles_required(Role.SUPER_ADMIN.value, Role.HR_ADMIN.value)
def update_employee(employee_id):
    employee = db.session.get(Employee, employee_id)
    if not employee:
        return jsonify({"error": "Employee not found."}), 404
    data, error = payload()
    if error:
        return error
    scalar_fields = {"firstName": "first_name", "lastName": "last_name", "phone": "phone", "active": "active",
                     "departmentId": "department_id", "designationId": "designation_id", "shiftId": "shift_id"}
    for api_name, model_name in scalar_fields.items():
        if api_name in data:
            setattr(employee, model_name, data[api_name])
    if "email" in data:
        email = data["email"].strip().lower()
        conflict = User.query.filter(User.email == email, User.id != employee.user_id).first()
        if conflict:
            return jsonify({"error": "Email already exists."}), 409
        employee.user.email = email
    add_audit_log(current_user().id, "employee_updated", "employee", employee.id, data, request.remote_addr)
    db.session.commit()
    return jsonify({"employee": employee.to_dict()})


@employees_bp.patch("/employees/me")
@roles_required(Role.SUPER_ADMIN.value, Role.HR_ADMIN.value, Role.EMPLOYEE.value)
def update_my_profile():
    """Let every signed-in user maintain their own basic contact profile."""
    employee = current_employee()
    if not employee:
        return jsonify({"error": "Employee profile not found."}), 404
    data, error = payload()
    if error:
        return error
    for api_name, model_name in {"firstName": "first_name", "lastName": "last_name", "phone": "phone"}.items():
        if api_name in data:
            value = data[api_name].strip() if isinstance(data[api_name], str) else data[api_name]
            if api_name in {"firstName", "lastName"} and not value:
                return jsonify({"error": f"{api_name} cannot be empty."}), 400
            setattr(employee, model_name, value)
    if "email" in data:
        email = data["email"].strip().lower()
        if not email:
            return jsonify({"error": "email cannot be empty."}), 400
        conflict = User.query.filter(User.email == email, User.id != employee.user_id).first()
        if conflict:
            return jsonify({"error": "Email already exists."}), 409
        employee.user.email = email
    add_audit_log(current_user().id, "profile_updated", "employee", employee.id, {"fields": list(data)}, request.remote_addr)
    db.session.commit()
    return jsonify({"employee": employee.to_dict(), "user": employee.user.to_dict()})


@employees_bp.delete("/employees/<int:employee_id>")
@roles_required(Role.SUPER_ADMIN.value)
def deactivate_employee(employee_id):
    employee = db.session.get(Employee, employee_id)
    if not employee:
        return jsonify({"error": "Employee not found."}), 404
    employee.active = False
    employee.user.is_active = False
    add_audit_log(current_user().id, "employee_deactivated", "employee", employee.id, ip_address=request.remote_addr)
    db.session.commit()
    return jsonify({"message": "Employee account deactivated."})


@employees_bp.post("/employees/me/biometric-consent")
@roles_required(Role.EMPLOYEE.value, Role.HR_ADMIN.value, Role.SUPER_ADMIN.value)
def set_biometric_consent():
    data, error = payload(("consent",))
    if error:
        return error
    employee = current_employee()
    if not employee:
        return jsonify({"error": "Employee profile is required."}), 400
    if data["consent"] is True:
        employee.biometric_consent_at = datetime.utcnow()
        action = "biometric_consent_granted"
    else:
        employee.biometric_consent_at = None
        for template in employee.face_templates:
            template.active = False
        action = "biometric_consent_withdrawn"
    add_audit_log(current_user().id, action, "employee", employee.id, ip_address=request.remote_addr)
    db.session.commit()
    return jsonify({"biometricConsentAt": employee.biometric_consent_at.isoformat() if employee.biometric_consent_at else None})


@employees_bp.get("/settings/reference-data")
@roles_required(Role.SUPER_ADMIN.value, Role.HR_ADMIN.value, Role.EMPLOYEE.value)
def reference_data():
    return jsonify({"departments": [item.to_dict() for item in Department.query.order_by(Department.name)],
                    "designations": [item.to_dict() for item in Designation.query.order_by(Designation.title)],
                    "shifts": [item.to_dict() for item in Shift.query.order_by(Shift.name)],
                    "holidays": [{"id": item.id, "name": item.name, "date": item.holiday_date.isoformat(), "optional": item.optional}
                                 for item in Holiday.query.order_by(Holiday.holiday_date)]})


@employees_bp.post("/settings/departments")
@roles_required(Role.SUPER_ADMIN.value, Role.HR_ADMIN.value)
def create_department():
    data, error = payload(("name", "code"))
    if error:
        return error
    item = Department(name=data["name"].strip(), code=data["code"].strip().upper())
    db.session.add(item)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Department name and code must be unique."}), 409
    return jsonify({"department": item.to_dict()}), 201


@employees_bp.post("/settings/designations")
@roles_required(Role.SUPER_ADMIN.value, Role.HR_ADMIN.value)
def create_designation():
    data, error = payload(("title",))
    if error:
        return error
    item = Designation(title=data["title"].strip())
    db.session.add(item)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Designation must be unique."}), 409
    return jsonify({"designation": item.to_dict()}), 201


@employees_bp.post("/settings/shifts")
@roles_required(Role.SUPER_ADMIN.value, Role.HR_ADMIN.value)
def create_shift():
    data, error = payload(("name", "startTime", "endTime"))
    if error:
        return error
    try:
        item = Shift(name=data["name"].strip(), start_time=time.fromisoformat(data["startTime"]),
                     end_time=time.fromisoformat(data["endTime"]), grace_minutes=int(data.get("graceMinutes", 10)),
                     full_day_minutes=int(data.get("fullDayMinutes", 480)), half_day_minutes=int(data.get("halfDayMinutes", 240)),
                     overtime_after_minutes=int(data.get("overtimeAfterMinutes", 480)))
    except (TypeError, ValueError):
        return jsonify({"error": "Shift times and policy minutes are invalid."}), 400
    db.session.add(item)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Shift name must be unique."}), 409
    return jsonify({"shift": item.to_dict()}), 201


@employees_bp.post("/settings/holidays")
@roles_required(Role.SUPER_ADMIN.value, Role.HR_ADMIN.value)
def create_holiday():
    data, error = payload(("name", "date"))
    if error:
        return error
    try:
        item = Holiday(name=data["name"].strip(), holiday_date=datetime.fromisoformat(data["date"]).date(), optional=bool(data.get("optional", False)))
    except ValueError:
        return jsonify({"error": "date must use YYYY-MM-DD format."}), 400
    db.session.add(item)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "A holiday already exists for this date."}), 409
    return jsonify({"holiday": {"id": item.id, "name": item.name, "date": item.holiday_date.isoformat(), "optional": item.optional}}), 201
