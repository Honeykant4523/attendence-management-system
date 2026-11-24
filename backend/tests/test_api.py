from datetime import date

import pytest

from app import create_app
from app.extensions import db
from app.models import LeaveBalance
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    JWT_SECRET_KEY = "test-jwt-secret"
    SECRET_KEY = "test-secret"


@pytest.fixture()
def client():
    app = create_app(TestConfig)
    with app.app_context():
        db.drop_all()
        db.create_all()
    with app.test_client() as test_client:
        yield test_client
    with app.app_context():
        db.session.remove()
        db.drop_all()


def auth_header(client):
    response = client.post("/api/auth/login", json={"email": "admin@example.test", "password": "long-test-password"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json['accessToken']}"}


def bootstrap(client):
    response = client.post("/api/auth/register", json={"email": "admin@example.test", "password": "long-test-password", "firstName": "Ada", "lastName": "Admin"})
    assert response.status_code == 201
    headers = auth_header(client)
    assert client.post("/api/settings/departments", json={"name": "Engineering", "code": "ENG"}, headers=headers).status_code == 201
    assert client.post("/api/settings/designations", json={"title": "Engineer"}, headers=headers).status_code == 201
    assert client.post("/api/settings/shifts", json={"name": "General", "startTime": "09:00", "endTime": "18:00"}, headers=headers).status_code == 201
    return headers


def test_admin_can_manage_attendance_and_export_report(client):
    headers = bootstrap(client)
    created = client.post("/api/employees", headers=headers, json={"email": "employee@example.test", "password": "employee-password", "firstName": "Eli", "lastName": "Employee", "departmentId": 1, "designationId": 1, "shiftId": 1})
    assert created.status_code == 201
    employee_id = created.json["employee"]["id"]
    check_in = client.post("/api/attendance/admin/check-in", headers=headers, json={"employeeId": employee_id, "at": f"{date.today().isoformat()}T09:03:00"})
    assert check_in.status_code == 201
    check_out = client.post("/api/attendance/admin/check-out", headers=headers, json={"employeeId": employee_id, "at": f"{date.today().isoformat()}T18:20:00"})
    assert check_out.status_code == 200
    assert check_out.json["attendance"]["workMinutes"] == 557
    dashboard = client.get("/api/dashboard", headers=headers)
    assert dashboard.status_code == 200
    assert dashboard.json["cards"]["presentToday"] == 1
    report = client.get("/api/reports/attendance/export/csv", headers=headers)
    assert report.status_code == 200
    assert b"Eli Employee" in report.data


def test_employee_cannot_read_organization_report(client):
    headers = bootstrap(client)
    created = client.post("/api/employees", headers=headers, json={"email": "employee@example.test", "password": "employee-password", "firstName": "Eli", "lastName": "Employee"})
    assert created.status_code == 201
    response = client.post("/api/auth/login", json={"email": "employee@example.test", "password": "employee-password"})
    employee_headers = {"Authorization": f"Bearer {response.json['accessToken']}"}
    own_report = client.get("/api/reports/attendance", headers=employee_headers)
    assert own_report.status_code == 200
    forbidden_people = client.get("/api/employees", headers=employee_headers)
    assert forbidden_people.status_code == 403


def test_leave_requires_approval_and_balance(client):
    headers = bootstrap(client)
    created = client.post("/api/employees", headers=headers, json={"email": "employee@example.test", "password": "employee-password", "firstName": "Eli", "lastName": "Employee"})
    employee_id = created.json["employee"]["id"]
    with client.application.app_context():
        db.session.add(LeaveBalance(employee_id=employee_id, leave_type="casual", year=date.today().year, allocated_days=10))
        db.session.commit()
    login = client.post("/api/auth/login", json={"email": "employee@example.test", "password": "employee-password"})
    employee_headers = {"Authorization": f"Bearer {login.json['accessToken']}"}
    tomorrow = date.today().fromordinal(date.today().toordinal() + 1).isoformat()
    applied = client.post("/api/leaves", headers=employee_headers, json={"leaveType": "casual", "startDate": tomorrow, "endDate": tomorrow, "reason": "Personal work"})
    assert applied.status_code == 201
    reviewed = client.post(f"/api/leaves/{applied.json['leave']['id']}/review", headers=headers, json={"decision": "approved"})
    assert reviewed.status_code == 200
    assert reviewed.json["leave"]["status"] == "approved"
