from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from flask import Blueprint, current_app, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models import Holiday, LeaveBalance, LeaveRequest, Role, add_audit_log
from ..utils.security import current_employee, current_user, roles_required
from ..utils.validation import parse_date, payload

leaves_bp = Blueprint("leaves", __name__)
ALLOWED_DOCUMENTS = {".pdf", ".png", ".jpg", ".jpeg"}


def _business_days(start: date, end: date) -> float:
    holiday_dates = {item.holiday_date for item in Holiday.query.filter(Holiday.holiday_date.between(start, end)).all()}
    days, pointer = 0, start
    while pointer <= end:
        if pointer.weekday() < 5 and pointer not in holiday_dates:
            days += 1
        pointer += timedelta(days=1)
    return float(days)


@leaves_bp.get("/leaves")
@roles_required(Role.SUPER_ADMIN.value, Role.HR_ADMIN.value, Role.EMPLOYEE.value)
def list_leaves():
    query = LeaveRequest.query
    if current_user().role == Role.EMPLOYEE.value:
        query = query.filter_by(employee_id=current_employee().id)
    if request.args.get("status"):
        query = query.filter_by(status=request.args["status"])
    return jsonify({"items": [item.to_dict() for item in query.order_by(LeaveRequest.created_at.desc()).all()]})


@leaves_bp.post("/leaves")
@roles_required(Role.SUPER_ADMIN.value, Role.HR_ADMIN.value, Role.EMPLOYEE.value)
def apply_leave():
    # Supports multipart/form-data for optional document upload and JSON for API clients.
    if request.content_type and request.content_type.startswith("multipart/"):
        data = request.form.to_dict()
        document = request.files.get("document")
    else:
        data, error = payload(("leaveType", "startDate", "endDate", "reason"))
        if error:
            return error
        document = None
    required = ("leaveType", "startDate", "endDate", "reason")
    if any(not data.get(item) for item in required):
        return jsonify({"error": "leaveType, startDate, endDate and reason are required."}), 400
    if data["leaveType"] not in {"paid", "sick", "casual"}:
        return jsonify({"error": "Unsupported leave type."}), 400
    try:
        start, end = parse_date(data["startDate"], "startDate"), parse_date(data["endDate"], "endDate")
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    if end < start or start < date.today():
        return jsonify({"error": "Leave dates are invalid."}), 400
    employee = current_employee()
    collision = LeaveRequest.query.filter(LeaveRequest.employee_id == employee.id, LeaveRequest.status.in_(("pending", "approved")),
                                          LeaveRequest.start_date <= end, LeaveRequest.end_date >= start).first()
    if collision:
        return jsonify({"error": "This leave overlaps an existing request."}), 409
    saved_path = None
    if document and document.filename:
        extension = Path(secure_filename(document.filename)).suffix.lower()
        if extension not in ALLOWED_DOCUMENTS:
            return jsonify({"error": "Only PDF, PNG, JPG and JPEG documents are allowed."}), 400
        filename = f"leave-{employee.id}-{uuid4().hex}{extension}"
        document.save(Path(current_app.config["UPLOAD_FOLDER"]) / filename)
        saved_path = filename
    leave = LeaveRequest(employee_id=employee.id, leave_type=data["leaveType"], start_date=start, end_date=end,
                         reason=data["reason"].strip(), document_path=saved_path)
    db.session.add(leave)
    add_audit_log(current_user().id, "leave_requested", "leave_request", None, {"days": _business_days(start, end)}, request.remote_addr)
    db.session.commit()
    return jsonify({"leave": leave.to_dict()}), 201


@leaves_bp.get("/leaves/balances")
@roles_required(Role.SUPER_ADMIN.value, Role.HR_ADMIN.value, Role.EMPLOYEE.value)
def leave_balances():
    employee = current_employee()
    year = request.args.get("year", date.today().year, type=int)
    balances = LeaveBalance.query.filter_by(employee_id=employee.id, year=year).all()
    return jsonify({"items": [item.to_dict() for item in balances]})


@leaves_bp.post("/leaves/<int:leave_id>/review")
@roles_required(Role.SUPER_ADMIN.value, Role.HR_ADMIN.value)
def review_leave(leave_id):
    data, error = payload(("decision",))
    if error:
        return error
    if data["decision"] not in {"approved", "rejected"}:
        return jsonify({"error": "decision must be approved or rejected."}), 400
    leave = db.session.get(LeaveRequest, leave_id)
    if not leave or leave.status != "pending":
        return jsonify({"error": "Pending leave request not found."}), 404
    if data["decision"] == "approved":
        days = _business_days(leave.start_date, leave.end_date)
        balance = LeaveBalance.query.filter_by(employee_id=leave.employee_id, leave_type=leave.leave_type, year=leave.start_date.year).first()
        if not balance or balance.allocated_days - balance.used_days < days:
            return jsonify({"error": "Insufficient leave balance for approval."}), 400
        balance.used_days += days
    leave.status = data["decision"]
    leave.reviewed_by_id = current_user().id
    leave.reviewed_at = datetime.utcnow()
    leave.reviewer_note = data.get("note", "").strip() or None
    add_audit_log(current_user().id, "leave_reviewed", "leave_request", leave.id, {"decision": leave.status}, request.remote_addr)
    db.session.commit()
    return jsonify({"leave": leave.to_dict()})


@leaves_bp.get("/leaves/<int:leave_id>/document")
@roles_required(Role.SUPER_ADMIN.value, Role.HR_ADMIN.value, Role.EMPLOYEE.value)
def get_document(leave_id):
    leave = db.session.get(LeaveRequest, leave_id)
    if not leave or not leave.document_path:
        return jsonify({"error": "Document not found."}), 404
    if current_user().role == Role.EMPLOYEE.value and leave.employee_id != current_employee().id:
        return jsonify({"error": "You may only access your own leave document."}), 403
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], leave.document_path, as_attachment=True)
