"""Create non-sensitive starter reference data for a new SmartAttend database."""
from datetime import time

from app import create_app
from app.extensions import db
from app.models import Department, Designation, Shift


app = create_app()

with app.app_context():
    for name, code in (("Engineering", "ENG"), ("Human Resources", "HR"), ("Operations", "OPS")):
        if not Department.query.filter_by(code=code).first():
            db.session.add(Department(name=name, code=code))
    for title in ("Software Engineer", "HR Manager", "Operations Executive"):
        if not Designation.query.filter_by(title=title).first():
            db.session.add(Designation(title=title))
    if not Shift.query.filter_by(name="General Shift").first():
        db.session.add(Shift(name="General Shift", start_time=time(9), end_time=time(18)))
    db.session.commit()
    print("Reference data created. Register the first super admin through the API or frontend.")
