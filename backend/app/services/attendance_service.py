from datetime import datetime, timedelta

from ..extensions import db
from ..models import Attendance, Employee, Holiday


def attendance_status_for_minutes(employee: Employee, minutes: int) -> str:
    shift = employee.shift
    if not shift:
        return "present"
    if minutes < shift.half_day_minutes:
        return "half_day"
    return "present"


def calculate_late_minutes(employee: Employee, checked_in: datetime) -> int:
    shift = employee.shift
    if not shift:
        return 0
    scheduled = datetime.combine(checked_in.date(), shift.start_time) + timedelta(minutes=shift.grace_minutes)
    return max(0, int((checked_in - scheduled).total_seconds() // 60))


def check_in(employee: Employee, at: datetime, method: str, verified: bool, remarks=None):
    if Holiday.query.filter_by(holiday_date=at.date()).first():
        raise ValueError("Attendance cannot be recorded on a configured holiday.")
    record = Attendance.query.filter_by(employee_id=employee.id, attendance_date=at.date()).first()
    if record and record.check_in_at:
        raise ValueError("A check-in has already been recorded for this day.")
    if not record:
        record = Attendance(employee_id=employee.id, attendance_date=at.date(), status="present")
        db.session.add(record)
    record.check_in_at = at
    record.check_in_method = method
    record.verified = verified
    record.late_minutes = calculate_late_minutes(employee, at)
    record.remarks = remarks or record.remarks
    return record


def check_out(employee: Employee, at: datetime, method: str):
    record = Attendance.query.filter_by(employee_id=employee.id, attendance_date=at.date()).first()
    if not record or not record.check_in_at:
        raise ValueError("A verified check-in is required before check-out.")
    if record.check_out_at:
        raise ValueError("A check-out has already been recorded for this day.")
    if at < record.check_in_at:
        raise ValueError("Check-out cannot occur before check-in.")
    record.check_out_at = at
    record.check_out_method = method
    record.work_minutes = max(0, int((at - record.check_in_at).total_seconds() // 60) - record.break_minutes)
    record.status = attendance_status_for_minutes(employee, record.work_minutes)
    threshold = employee.shift.overtime_after_minutes if employee.shift else 480
    record.overtime_minutes = max(0, record.work_minutes - threshold)
    return record
