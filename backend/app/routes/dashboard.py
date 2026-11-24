from calendar import monthrange
from datetime import date, timedelta

from flask import Blueprint, jsonify
from sqlalchemy import func

from ..extensions import db
from ..models import Attendance, Department, Employee, LeaveRequest, Role
from ..services.analytics_service import department_trends, employee_insights
from ..utils.security import current_employee, current_user, roles_required

dashboard_bp = Blueprint("dashboard", __name__)


def _minutes_to_hours(minutes):
    return round(minutes / 60, 1)


@dashboard_bp.get("/dashboard")
@roles_required(Role.SUPER_ADMIN.value, Role.HR_ADMIN.value, Role.EMPLOYEE.value)
def dashboard():
    today = date.today()
    user = current_user()
    if user.role == Role.EMPLOYEE.value:
        employee = current_employee()
        record = Attendance.query.filter_by(employee_id=employee.id, attendance_date=today).first()
        monthly = Attendance.query.filter(Attendance.employee_id == employee.id,
                                          Attendance.attendance_date >= today.replace(day=1),
                                          Attendance.attendance_date <= today).all()
        working = sum(item.work_minutes for item in monthly)
        return jsonify({"scope": "employee", "today": record.to_dict() if record else None,
                        "summary": {"totalWorkingHours": _minutes_to_hours(working),
                                    "attendanceDays": sum(item.status == "present" for item in monthly),
                                    "lateDays": sum(item.late_minutes > 0 for item in monthly)},
                        "recentAttendance": [item.to_dict() for item in sorted(monthly, key=lambda row: row.attendance_date, reverse=True)[:7]]})

    active_employees = Employee.query.filter_by(active=True).count()
    records = Attendance.query.filter_by(attendance_date=today).all()
    on_leave = LeaveRequest.query.filter(LeaveRequest.status == "approved", LeaveRequest.start_date <= today,
                                         LeaveRequest.end_date >= today).count()
    present = sum(row.status == "present" and row.check_in_at is not None for row in records)
    late = sum(row.late_minutes > 0 for row in records)
    checked_employee_ids = {row.employee_id for row in records}
    absent = max(0, active_employees - len(checked_employee_ids) - on_leave)
    days_in_month = monthrange(today.year, today.month)[1]
    start_of_month = today.replace(day=1)
    monthly_records = Attendance.query.filter(Attendance.attendance_date >= start_of_month, Attendance.attendance_date <= today).all()
    by_day = {day: 0 for day in range(1, today.day + 1)}
    for row in monthly_records:
        if row.status == "present":
            by_day[row.attendance_date.day] += 1
    departments = []
    for department in Department.query.order_by(Department.name).all():
        size = sum(employee.active for employee in department.employees)
        department_present = sum(row.status == "present" and row.employee.department_id == department.id for row in records)
        departments.append({"department": department.name, "employees": size, "present": department_present,
                            "percentage": round(department_present / size * 100, 1) if size else 0})
    return jsonify({"scope": "admin", "cards": {"totalEmployees": active_employees, "activeEmployees": active_employees,
                    "presentToday": present, "absentToday": absent, "onLeave": on_leave, "lateArrivals": late,
                    "attendancePercentage": round((present / active_employees) * 100, 1) if active_employees else 0},
                    "monthlyAttendance": [{"day": f"{today.year}-{today.month:02d}-{day:02d}", "present": count} for day, count in by_day.items()],
                    "departmentAttendance": departments,
                    "recentAttendance": [row.to_dict() for row in Attendance.query.order_by(Attendance.updated_at.desc()).limit(8).all()]})


@dashboard_bp.get("/insights")
@roles_required(Role.SUPER_ADMIN.value, Role.HR_ADMIN.value)
def insights():
    return jsonify({"label": "Predictions are advisory signals based on recorded history and do not alter attendance.",
                    "employeePredictions": employee_insights(), "departmentActuals": department_trends()})
