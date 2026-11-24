"""Explainable attendance signals. These are predictions, never attendance records."""
from collections import defaultdict
from datetime import date, timedelta

import numpy as np

from ..models import Attendance, Employee


def employee_insights(days=90):
    start = date.today() - timedelta(days=days)
    employees = Employee.query.filter_by(active=True).all()
    insights = []
    for employee in employees:
        rows = Attendance.query.filter(Attendance.employee_id == employee.id, Attendance.attendance_date >= start).all()
        if not rows:
            continue
        completed = [row for row in rows if row.status not in {"leave", "holiday"}]
        if not completed:
            continue
        late_rate = sum(row.late_minutes > 0 for row in completed) / len(completed)
        short_day_rate = sum(row.status == "half_day" for row in completed) / len(completed)
        # Transparent risk proxy: enough data and recurring late/short-day signals.
        risk = min(0.95, 0.15 + late_rate * 0.5 + short_day_rate * 0.35)
        if risk >= 0.42:
            insights.append({"employeeId": employee.id, "employee": employee.full_name,
                             "type": "attendance_irregularity_risk", "riskScore": round(risk, 2),
                             "explanation": f"Based on {len(completed)} recorded days: {late_rate:.0%} late arrivals and {short_day_rate:.0%} short days.",
                             "isPrediction": True})
    return sorted(insights, key=lambda item: item["riskScore"], reverse=True)


def department_trends(days=90):
    start = date.today() - timedelta(days=days)
    aggregate = defaultdict(lambda: {"records": 0, "late": 0, "present": 0})
    for row in Attendance.query.join(Employee).filter(Attendance.attendance_date >= start).all():
        name = row.employee.department.name if row.employee.department else "Unassigned"
        aggregate[name]["records"] += 1
        aggregate[name]["late"] += int(row.late_minutes > 0)
        aggregate[name]["present"] += int(row.status == "present")
    return [{"department": name, "recordedDays": value["records"],
             "lateArrivalRate": round(value["late"] / value["records"], 2) if value["records"] else 0,
             "presentRate": round(value["present"] / value["records"], 2) if value["records"] else 0,
             "isPrediction": False} for name, value in aggregate.items()]
