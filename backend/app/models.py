from datetime import date, datetime
from enum import Enum

from sqlalchemy import CheckConstraint, Index, UniqueConstraint
from sqlalchemy.orm import validates

from .extensions import bcrypt, db


class Role(str, Enum):
    SUPER_ADMIN = "super_admin"
    HR_ADMIN = "hr_admin"
    EMPLOYEE = "employee"


class TimestampMixin:
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class User(TimestampMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), nullable=False, default=Role.EMPLOYEE.value, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    employee = db.relationship("Employee", back_populates="user", uselist=False, cascade="all, delete-orphan")

    def set_password(self, password: str):
        self.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

    def check_password(self, password: str) -> bool:
        return bcrypt.check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {"id": self.id, "email": self.email, "role": self.role, "isActive": self.is_active}


class Department(TimestampMixin, db.Model):
    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    employees = db.relationship("Employee", back_populates="department")

    def to_dict(self):
        return {"id": self.id, "name": self.name, "code": self.code}


class Designation(TimestampMixin, db.Model):
    __tablename__ = "designations"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), unique=True, nullable=False)
    employees = db.relationship("Employee", back_populates="designation")

    def to_dict(self):
        return {"id": self.id, "title": self.title}


class Shift(TimestampMixin, db.Model):
    __tablename__ = "shifts"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    grace_minutes = db.Column(db.Integer, nullable=False, default=10)
    full_day_minutes = db.Column(db.Integer, nullable=False, default=480)
    half_day_minutes = db.Column(db.Integer, nullable=False, default=240)
    overtime_after_minutes = db.Column(db.Integer, nullable=False, default=480)
    employees = db.relationship("Employee", back_populates="shift")

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "startTime": self.start_time.isoformat(),
            "endTime": self.end_time.isoformat(), "graceMinutes": self.grace_minutes,
            "fullDayMinutes": self.full_day_minutes, "halfDayMinutes": self.half_day_minutes,
        }


class Employee(TimestampMixin, db.Model):
    __tablename__ = "employees"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    employee_code = db.Column(db.String(30), unique=True, nullable=False, index=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(30))
    join_date = db.Column(db.Date, nullable=False, default=date.today)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id", ondelete="SET NULL"))
    designation_id = db.Column(db.Integer, db.ForeignKey("designations.id", ondelete="SET NULL"))
    shift_id = db.Column(db.Integer, db.ForeignKey("shifts.id", ondelete="SET NULL"))
    manager_id = db.Column(db.Integer, db.ForeignKey("employees.id", ondelete="SET NULL"))
    biometric_consent_at = db.Column(db.DateTime)
    active = db.Column(db.Boolean, default=True, nullable=False)

    user = db.relationship("User", back_populates="employee")
    department = db.relationship("Department", back_populates="employees")
    designation = db.relationship("Designation", back_populates="employees")
    shift = db.relationship("Shift", back_populates="employees")
    manager = db.relationship("Employee", remote_side=[id], backref="direct_reports")
    attendance_records = db.relationship("Attendance", back_populates="employee", cascade="all, delete-orphan")
    leave_requests = db.relationship("LeaveRequest", back_populates="employee", cascade="all, delete-orphan")
    leave_balances = db.relationship("LeaveBalance", back_populates="employee", cascade="all, delete-orphan")
    face_templates = db.relationship("FaceTemplate", back_populates="employee", cascade="all, delete-orphan")

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def to_dict(self, include_email=True):
        result = {
            "id": self.id, "employeeCode": self.employee_code, "firstName": self.first_name,
            "lastName": self.last_name, "fullName": self.full_name, "phone": self.phone,
            "joinDate": self.join_date.isoformat(), "active": self.active,
            "department": self.department.to_dict() if self.department else None,
            "designation": self.designation.to_dict() if self.designation else None,
            "shift": self.shift.to_dict() if self.shift else None,
            "biometricConsentAt": self.biometric_consent_at.isoformat() if self.biometric_consent_at else None,
        }
        if include_email:
            result["email"] = self.user.email
        return result


class Attendance(TimestampMixin, db.Model):
    __tablename__ = "attendance"
    __table_args__ = (
        UniqueConstraint("employee_id", "attendance_date", name="uq_attendance_employee_date"),
        Index("ix_attendance_date_status", "attendance_date", "status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    attendance_date = db.Column(db.Date, nullable=False, default=date.today)
    check_in_at = db.Column(db.DateTime)
    check_out_at = db.Column(db.DateTime)
    status = db.Column(db.String(20), nullable=False, default="present")  # present/absent/leave/half_day/holiday
    check_in_method = db.Column(db.String(30))  # face/manual/admin
    check_out_method = db.Column(db.String(30))
    late_minutes = db.Column(db.Integer, nullable=False, default=0)
    work_minutes = db.Column(db.Integer, nullable=False, default=0)
    break_minutes = db.Column(db.Integer, nullable=False, default=0)
    overtime_minutes = db.Column(db.Integer, nullable=False, default=0)
    remarks = db.Column(db.String(500))
    verified = db.Column(db.Boolean, nullable=False, default=False)

    employee = db.relationship("Employee", back_populates="attendance_records")

    def to_dict(self):
        return {
            "id": self.id, "employee": self.employee.to_dict() if self.employee else None,
            "date": self.attendance_date.isoformat(), "checkInAt": self.check_in_at.isoformat() if self.check_in_at else None,
            "checkOutAt": self.check_out_at.isoformat() if self.check_out_at else None,
            "status": self.status, "checkInMethod": self.check_in_method, "checkOutMethod": self.check_out_method,
            "lateMinutes": self.late_minutes, "workMinutes": self.work_minutes,
            "breakMinutes": self.break_minutes, "overtimeMinutes": self.overtime_minutes,
            "remarks": self.remarks, "verified": self.verified,
        }


class LeaveRequest(TimestampMixin, db.Model):
    __tablename__ = "leave_requests"
    __table_args__ = (CheckConstraint("end_date >= start_date", name="ck_leave_dates"),)

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    leave_type = db.Column(db.String(30), nullable=False)  # paid/sick/casual
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.String(1000), nullable=False)
    document_path = db.Column(db.String(500))
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at = db.Column(db.DateTime)
    reviewer_note = db.Column(db.String(500))

    employee = db.relationship("Employee", back_populates="leave_requests")
    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_id])

    def to_dict(self):
        return {
            "id": self.id, "employee": self.employee.to_dict() if self.employee else None,
            "leaveType": self.leave_type, "startDate": self.start_date.isoformat(), "endDate": self.end_date.isoformat(),
            "reason": self.reason, "status": self.status, "documentAvailable": bool(self.document_path),
            "reviewerNote": self.reviewer_note, "reviewedAt": self.reviewed_at.isoformat() if self.reviewed_at else None,
        }


class LeaveBalance(TimestampMixin, db.Model):
    __tablename__ = "leave_balances"
    __table_args__ = (UniqueConstraint("employee_id", "leave_type", "year", name="uq_leave_balance"),)

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    leave_type = db.Column(db.String(30), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    allocated_days = db.Column(db.Float, nullable=False, default=0)
    used_days = db.Column(db.Float, nullable=False, default=0)

    employee = db.relationship("Employee", back_populates="leave_balances")

    def to_dict(self):
        return {"leaveType": self.leave_type, "year": self.year, "allocatedDays": self.allocated_days,
                "usedDays": self.used_days, "remainingDays": max(0, self.allocated_days - self.used_days)}


class Holiday(TimestampMixin, db.Model):
    __tablename__ = "holidays"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    holiday_date = db.Column(db.Date, unique=True, nullable=False, index=True)
    optional = db.Column(db.Boolean, nullable=False, default=False)


class FaceTemplate(TimestampMixin, db.Model):
    __tablename__ = "face_templates"
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    encrypted_embedding = db.Column(db.LargeBinary, nullable=False)
    algorithm_version = db.Column(db.String(50), nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=True)
    consent_version = db.Column(db.String(30), nullable=False)

    employee = db.relationship("Employee", back_populates="face_templates")


class AttendanceCorrection(TimestampMixin, db.Model):
    __tablename__ = "attendance_corrections"
    id = db.Column(db.Integer, primary_key=True)
    attendance_id = db.Column(db.Integer, db.ForeignKey("attendance.id", ondelete="CASCADE"), nullable=False)
    requested_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    reason = db.Column(db.String(1000), nullable=False)
    requested_check_in = db.Column(db.DateTime)
    requested_check_out = db.Column(db.DateTime)
    status = db.Column(db.String(20), nullable=False, default="pending")
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))


class Notification(TimestampMixin, db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False)
    body = db.Column(db.String(500), nullable=False)
    read_at = db.Column(db.DateTime)


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), index=True)
    action = db.Column(db.String(100), nullable=False)
    entity_type = db.Column(db.String(100), nullable=False)
    entity_id = db.Column(db.String(100))
    details = db.Column(db.JSON)
    ip_address = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)


class PasswordResetToken(db.Model):
    """Store only token hashes; production delivery is handled by the mail provider."""
    __tablename__ = "password_reset_tokens"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = db.Column(db.String(128), nullable=False, unique=True)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    used_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


def add_audit_log(user_id, action, entity_type, entity_id=None, details=None, ip_address=None):
    db.session.add(AuditLog(user_id=user_id, action=action, entity_type=entity_type,
                            entity_id=str(entity_id) if entity_id else None, details=details, ip_address=ip_address))
