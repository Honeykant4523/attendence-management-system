from datetime import date
from io import BytesIO, StringIO

import pandas as pd
from flask import Blueprint, Response, jsonify, request, send_file
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

from ..models import Attendance, Role
from ..utils.security import can_access_employee, current_employee, current_user, roles_required
from ..utils.validation import parse_date

reports_bp = Blueprint("reports", __name__)


def _records_from_filters():
    employee_id = request.args.get("employeeId", type=int)
    if current_user().role == Role.EMPLOYEE.value:
        employee_id = current_employee().id
    elif employee_id and not can_access_employee(employee_id):
        raise PermissionError
    query = Attendance.query
    if employee_id:
        query = query.filter(Attendance.employee_id == employee_id)
    try:
        if request.args.get("from"):
            query = query.filter(Attendance.attendance_date >= parse_date(request.args["from"], "from"))
        if request.args.get("to"):
            query = query.filter(Attendance.attendance_date <= parse_date(request.args["to"], "to"))
    except ValueError as error:
        raise ValueError(str(error)) from error
    return query.order_by(Attendance.attendance_date.desc()).limit(5000).all()


def _rows(records):
    return [{"Date": row.attendance_date.isoformat(), "Employee ID": row.employee.employee_code, "Employee": row.employee.full_name,
             "Department": row.employee.department.name if row.employee.department else "Unassigned", "Status": row.status,
             "Check in": row.check_in_at.strftime("%H:%M") if row.check_in_at else "", "Check out": row.check_out_at.strftime("%H:%M") if row.check_out_at else "",
             "Work hours": round(row.work_minutes / 60, 2), "Late minutes": row.late_minutes, "Overtime hours": round(row.overtime_minutes / 60, 2),
             "Verified": "Yes" if row.verified else "No"} for row in records]


@reports_bp.get("/reports/attendance")
@roles_required(Role.SUPER_ADMIN.value, Role.HR_ADMIN.value, Role.EMPLOYEE.value)
def attendance_report():
    try:
        rows = _rows(_records_from_filters())
    except PermissionError:
        return jsonify({"error": "You may only access your own reports."}), 403
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    return jsonify({"items": rows, "summary": {"records": len(rows), "present": sum(row["Status"] == "present" for row in rows),
                    "lateArrivals": sum(row["Late minutes"] > 0 for row in rows), "overtimeHours": round(sum(row["Overtime hours"] for row in rows), 2)}})


@reports_bp.get("/reports/attendance/export/<format>")
@roles_required(Role.SUPER_ADMIN.value, Role.HR_ADMIN.value, Role.EMPLOYEE.value)
def export_attendance_report(format):
    if format not in {"csv", "xlsx", "pdf"}:
        return jsonify({"error": "Supported formats are csv, xlsx and pdf."}), 400
    try:
        rows = _rows(_records_from_filters())
    except PermissionError:
        return jsonify({"error": "You may only access your own reports."}), 403
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    dataframe = pd.DataFrame(rows)
    filename = f"smartattend-attendance-{date.today().isoformat()}.{format}"
    if format == "csv":
        return Response(dataframe.to_csv(index=False), mimetype="text/csv", headers={"Content-Disposition": f"attachment; filename={filename}"})
    if format == "xlsx":
        binary = BytesIO()
        with pd.ExcelWriter(binary, engine="openpyxl") as writer:
            dataframe.to_excel(writer, index=False, sheet_name="Attendance")
            sheet = writer.book["Attendance"]
            sheet.freeze_panes = "A2"
            for column in sheet.columns:
                sheet.column_dimensions[column[0].column_letter].width = min(28, max(12, max(len(str(cell.value or "")) for cell in column) + 2))
        binary.seek(0)
        return send_file(binary, as_attachment=True, download_name=filename,
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    binary = BytesIO()
    document = SimpleDocTemplate(binary, pagesize=landscape(A4), title="SmartAttend attendance report")
    table_data = [list(dataframe.columns)] + dataframe.fillna("").astype(str).values.tolist()
    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#12324a")),
                               ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                               ("FONTSIZE", (0, 0), (-1, -1), 7), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    document.build([table])
    binary.seek(0)
    return send_file(binary, as_attachment=True, download_name=filename, mimetype="application/pdf")
