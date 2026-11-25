from datetime import date, datetime

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import and_

from ..extensions import db
from ..models import Attendance, AttendanceCorrection, Employee, Role, User, add_audit_log
from ..services.attendance_service import check_in, check_out
from ..services.biometric_service import (BiometricUnavailable, basic_liveness_verified,
                                          create_template, embedding_from_image, match_employee)
from ..utils.security import can_access_employee, current_employee, current_user, roles_required
from ..utils.validation import parse_date, parse_datetime, payload

attendance_bp = Blueprint("attendance", __name__)


def _now_or_payload(data):
    return parse_datetime(data["at"], "at") if data.get("at") else datetime.now()


@attendance_bp.get("/attendance")
@roles_required(Role.SUPER_ADMIN.value, Role.HR_ADMIN.value, Role.EMPLOYEE.value)
def list_attendance():
    employee_id = request.args.get("employeeId", type=int)
    if not employee_id:
        employee = current_employee()
        employee_id = employee.id if employee else None
    if not employee_id or not can_access_employee(employee_id):
        return jsonify({"error": "You may only access your own attendance."}), 403
    query = Attendance.query.filter_by(employee_id=employee_id)
    try:
        if request.args.get("from"):
            query = query.filter(Attendance.attendance_date >= parse_date(request.args["from"], "from"))
        if request.args.get("to"):
            query = query.filter(Attendance.attendance_date <= parse_date(request.args["to"], "to"))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    records = query.order_by(Attendance.attendance_date.desc()).limit(366).all()
    return jsonify({"items": [record.to_dict() for record in records]})


@attendance_bp.post("/attendance/admin/check-in")
@roles_required(Role.SUPER_ADMIN.value, Role.HR_ADMIN.value)
def admin_check_in():
    data, error = payload(("employeeId",))
    if error:
        return error
    employee = db.session.get(Employee, data["employeeId"])
    if not employee:
        return jsonify({"error": "Employee not found."}), 404
    try:
        record = check_in(employee, _now_or_payload(data), "admin", True, data.get("remarks"))
        add_audit_log(current_user().id, "attendance_admin_check_in", "attendance", employee.id, {"record": record.attendance_date.isoformat()}, request.remote_addr)
        db.session.commit()
        return jsonify({"attendance": record.to_dict()}), 201
    except ValueError as err:
        return jsonify({"error": str(err)}), 400


@attendance_bp.post("/attendance/admin/check-out")
@roles_required(Role.SUPER_ADMIN.value, Role.HR_ADMIN.value)
def admin_check_out():
    data, error = payload(("employeeId",))
    if error:
        return error
    employee = db.session.get(Employee, data["employeeId"])
    if not employee:
        return jsonify({"error": "Employee not found."}), 404
    try:
        record = check_out(employee, _now_or_payload(data), "admin")
        add_audit_log(current_user().id, "attendance_admin_check_out", "attendance", record.id, ip_address=request.remote_addr)
        db.session.commit()
        return jsonify({"attendance": record.to_dict()})
    except ValueError as err:
        return jsonify({"error": str(err)}), 400


@attendance_bp.post("/attendance/manual-request")
@roles_required(Role.EMPLOYEE.value, Role.HR_ADMIN.value, Role.SUPER_ADMIN.value)
def manual_attendance_request():
    data, error = payload(("reason",))
    if error:
        return error
    employee = current_employee()
    if not employee:
        return jsonify({"error": "Employee profile not found."}), 400
    at = _now_or_payload(data)
    record = Attendance.query.filter_by(employee_id=employee.id, attendance_date=at.date()).first()
    correction = AttendanceCorrection(attendance_id=record.id if record else None, requested_by_id=current_user().id,
                                      reason=data["reason"].strip(), requested_check_in=at if data.get("kind", "check_in") == "check_in" else None,
                                      requested_check_out=at if data.get("kind") == "check_out" else None)
    db.session.add(correction)
    kind = data.get("kind", "check_in")
    if current_app.config["AUTO_APPROVE_MANUAL_ATTENDANCE"]:
        try:
            record = (check_in(employee, at, "manual_auto_approved", True, correction.reason)
                      if kind == "check_in" else check_out(employee, at, "manual_auto_approved"))
            db.session.flush()
            correction.attendance_id = record.id
            correction.status = "approved"
            # The requester is recorded as the actor because no separate reviewer was involved.
            correction.reviewed_by_id = current_user().id
            add_audit_log(current_user().id, "manual_attendance_auto_approved", "attendance_correction", correction.id,
                          {"kind": kind}, request.remote_addr)
            db.session.commit()
            return jsonify({"message": "Attendance recorded automatically.", "requestId": correction.id,
                            "attendance": record.to_dict()}), 201
        except ValueError as err:
            db.session.rollback()
            return jsonify({"error": str(err)}), 400
    add_audit_log(current_user().id, "manual_attendance_requested", "attendance_correction", None, {"kind": kind}, request.remote_addr)
    db.session.commit()
    return jsonify({"message": "Manual attendance request submitted for HR authorization.", "requestId": correction.id}), 202


@attendance_bp.get("/attendance/corrections")
@roles_required(Role.SUPER_ADMIN.value, Role.HR_ADMIN.value)
def list_corrections():
    status = request.args.get("status", "pending")
    corrections = AttendanceCorrection.query.filter_by(status=status).order_by(AttendanceCorrection.created_at.desc()).all()
    return jsonify({"items": [{"id": item.id, "status": item.status, "reason": item.reason,
                                "requestedCheckIn": item.requested_check_in.isoformat() if item.requested_check_in else None,
                                "requestedCheckOut": item.requested_check_out.isoformat() if item.requested_check_out else None,
                                "requestedBy": item.requested_by_id} for item in corrections]})


@attendance_bp.post("/attendance/corrections/<int:correction_id>/review")
@roles_required(Role.SUPER_ADMIN.value, Role.HR_ADMIN.value)
def review_correction(correction_id):
    data, error = payload(("decision",))
    if error:
        return error
    correction = db.session.get(AttendanceCorrection, correction_id)
    if not correction or correction.status != "pending":
        return jsonify({"error": "Pending correction request not found."}), 404
    if data["decision"] not in {"approved", "rejected"}:
        return jsonify({"error": "Decision must be approved or rejected."}), 400
    correction.status, correction.reviewed_by_id = data["decision"], current_user().id
    if correction.status == "approved":
        requester_user = db.session.get(User, correction.requested_by_id)
        requester = requester_user.employee if requester_user else None
        if not requester:
            return jsonify({"error": "The requesting employee no longer exists."}), 404
        try:
            if correction.requested_check_in:
                record = check_in(requester, correction.requested_check_in, "manual_authorized", True, correction.reason)
            else:
                record = check_out(requester, correction.requested_check_out, "manual_authorized")
            db.session.flush()
            correction.attendance_id = record.id
        except ValueError as err:
            db.session.rollback()
            return jsonify({"error": str(err)}), 400
    add_audit_log(current_user().id, "attendance_correction_reviewed", "attendance_correction", correction.id, {"decision": correction.status}, request.remote_addr)
    db.session.commit()
    return jsonify({"message": f"Request {correction.status}."})


@attendance_bp.post("/biometrics/enrol")
@roles_required(Role.EMPLOYEE.value, Role.HR_ADMIN.value, Role.SUPER_ADMIN.value)
def enrol_face():
    data, error = payload(("image",))
    if error:
        return error
    employee = current_employee()
    try:
        template = create_template(employee, data["image"], data.get("consentVersion", "v1"))
        db.session.add(template)
        add_audit_log(current_user().id, "biometric_template_enrolled", "employee", employee.id, ip_address=request.remote_addr)
        db.session.commit()
        return jsonify({"message": "Face template enrolled securely."}), 201
    except (BiometricUnavailable, ValueError) as err:
        return jsonify({"error": str(err)}), 400


@attendance_bp.post("/biometrics/verify-attendance")
@roles_required(Role.EMPLOYEE.value, Role.HR_ADMIN.value, Role.SUPER_ADMIN.value)
def verify_face_attendance():
    data, error = payload(("image", "frames", "action"))
    if error:
        return error
    if data["action"] not in {"check_in", "check_out"}:
        return jsonify({"error": "action must be check_in or check_out."}), 400
    employee = current_employee()
    try:
        if not employee.biometric_consent_at:
            return jsonify({"error": "Biometric consent is required; use the manual attendance fallback instead."}), 403
        if not basic_liveness_verified(data["frames"]):
            return jsonify({"error": "Liveness verification failed. No attendance was recorded; use manual fallback."}), 422
        distance = match_employee(employee, embedding_from_image(data["image"]))
        if distance is None:
            return jsonify({"error": "Face match could not be verified. No attendance was recorded; use manual fallback."}), 422
        at = _now_or_payload(data)
        record = check_in(employee, at, "face", True) if data["action"] == "check_in" else check_out(employee, at, "face")
        add_audit_log(current_user().id, f"face_{data['action']}", "attendance", record.id,
                      {"matchDistance": round(distance, 3)}, request.remote_addr)
        db.session.commit()
        return jsonify({"attendance": record.to_dict(), "matchConfidence": round(max(0, 1 - distance), 3)})
    except (BiometricUnavailable, ValueError) as err:
        return jsonify({"error": str(err)}), 400
