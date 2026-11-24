from datetime import date

from flask import Blueprint, jsonify

from ..models import Attendance, Employee, LeaveBalance, Role
from ..utils.security import current_employee, current_user, roles_required
from ..utils.validation import payload

chatbot_bp = Blueprint("chatbot", __name__)


def _attendance_percentage(employee):
    rows = Attendance.query.filter_by(employee_id=employee.id).all()
    eligible = [row for row in rows if row.status not in {"leave", "holiday"}]
    return round(100 * sum(row.status == "present" for row in eligible) / len(eligible), 1) if eligible else 0


@chatbot_bp.post("/chat")
@roles_required(Role.SUPER_ADMIN.value, Role.HR_ADMIN.value, Role.EMPLOYEE.value)
def chat():
    data, error = payload(("message",))
    if error:
        return error
    question = data["message"].lower().strip()
    user = current_user()
    employee = current_employee()
    today = date.today()
    is_admin = user.role in {Role.SUPER_ADMIN.value, Role.HR_ADMIN.value}

    if "present" in question and ("how many" in question or "count" in question):
        if is_admin:
            count = Attendance.query.filter_by(attendance_date=today, status="present").filter(Attendance.check_in_at.isnot(None)).count()
            answer = f"{count} employees have a verified present record today."
        else:
            record = Attendance.query.filter_by(employee_id=employee.id, attendance_date=today).first()
            answer = "You are marked present today." if record and record.status == "present" else "You do not have a present record today."
    elif "absent" in question and is_admin:
        checked = {item.employee_id for item in Attendance.query.filter_by(attendance_date=today).all()}
        absent = Employee.query.filter_by(active=True).filter(~Employee.id.in_(checked)).all() if checked else Employee.query.filter_by(active=True).all()
        answer = "Absent/no-record employees today: " + (", ".join(item.full_name for item in absent[:20]) or "none") + "."
    elif "late" in question:
        query = Attendance.query.filter_by(attendance_date=today).filter(Attendance.late_minutes > 0)
        if not is_admin:
            query = query.filter_by(employee_id=employee.id)
        entries = query.all()
        answer = "Late arrivals today: " + (", ".join(f"{item.employee.full_name} ({item.late_minutes}m)" for item in entries) or "none") + "."
    elif "percentage" in question or "attendance rate" in question:
        if not employee:
            answer = "No linked employee record is available."
        else:
            answer = f"Your recorded attendance percentage is {_attendance_percentage(employee)}%."
    elif "history" in question:
        rows = Attendance.query.filter_by(employee_id=employee.id).order_by(Attendance.attendance_date.desc()).limit(5).all()
        answer = "Your latest records: " + (", ".join(f"{row.attendance_date.isoformat()} ({row.status})" for row in rows) or "no records yet") + "."
    elif "leave" in question and ("remaining" in question or "balance" in question):
        balances = LeaveBalance.query.filter_by(employee_id=employee.id, year=today.year).all()
        answer = "Your remaining leave: " + (", ".join(f"{item.leave_type}: {item.allocated_days - item.used_days:g} days" for item in balances) or "no leave balances are configured") + "."
    elif "report" in question:
        answer = "You can export your authorized attendance report from Reports as CSV, Excel, or PDF."
    elif "department" in question and "absenteeism" in question and is_admin:
        departments = {}
        for item in Employee.query.filter_by(active=True).all():
            department = item.department.name if item.department else "Unassigned"
            departments.setdefault(department, [0, 0])[0] += 1
            departments[department][1] += int(Attendance.query.filter_by(employee_id=item.id, attendance_date=today, status="present").count() == 0)
        ranked = sorted(departments.items(), key=lambda item: item[1][1] / item[1][0] if item[1][0] else 0, reverse=True)
        answer = "Today’s highest no-record rate: " + (f"{ranked[0][0]} ({ranked[0][1][1]}/{ranked[0][1][0]} employees)" if ranked else "no department data") + "."
    else:
        answer = "I can help with authorized attendance totals, late arrivals, your attendance history, leave balance, reports, and department absenteeism for HR users."
    return jsonify({"answer": answer, "authorizedScope": "organization" if is_admin else "personal"})
