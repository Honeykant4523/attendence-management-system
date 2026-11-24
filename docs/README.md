# SmartAttend

SmartAttend is a full-stack attendance-management application for super admins, HR admins, and employees. It uses a React/Vite SaaS dashboard with a Flask REST API, JWT authentication, SQLAlchemy, and a MySQL-compatible normalized data model.

## What is implemented

- Role-based JWT sign-in, secure password hashing, first-account super-admin bootstrap, password-reset tokens, account audit records, and protected routes.
- Employee directory, departments, designations, shifts, holiday configuration, employee IDs, deactivation, and profile access rules.
- Check-in/check-out, late/grace calculations, work/overtime/half-day calculations, HR-authorized manual requests, corrections, holidays, and duplicate-attendance prevention.
- Leave requests with approval, balance consumption, collision checks, document uploads, and access-controlled downloads.
- Live dashboards, Recharts visualizations, explainable historical attendance signals, role-filtered HR chatbot, and CSV/XLSX/PDF exports.
- An opt-in biometric integration boundary: encrypted face templates, no attendance on unverified face matches, multi-frame basic liveness gate, template deactivation on consent withdrawal, and a manual HR-authorized fallback.

## Architecture and workflow

```text
React + Tailwind UI  ──JWT──>  Flask API  ──SQLAlchemy──>  MySQL
       │                              │
       ├── dashboards/reports          ├── attendance + leave policy services
       └── face camera (opt-in)        ├── biometric adapter (optional runtime)
                                      └── analytics / chatbot query layer
```

1. The first registered account is automatically a `super_admin`; subsequent registrations require a super-admin token.
2. An admin configures reference data, creates employee accounts, and assigns shifts.
3. Employees use registered, consented biometric verification or request manual attendance. HR authorization is required for manual requests.
4. Check-out computes work hours, half-day status, and overtime from the assigned shift.
5. Leave and report actions use the same database records. AI insights are clearly presented as advisory historical signals only.

## Local setup (PowerShell)

Prerequisites: Python 3.11+ (the project was verified on 3.13), Node.js 20+, and optionally MySQL 8.

```powershell
Copy-Item .env.example backend\.env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
python backend\seed.py

Copy-Item frontend\.env.example frontend\.env
Set-Location frontend
npm install
npm run dev
```

In a second terminal:

```powershell
.\.venv\Scripts\Activate.ps1
Set-Location backend
python app.py
```

Open `http://localhost:5173`. The initial sign-up request can be made with the API (or a one-time onboarding screen can be added for your deployment):

```powershell
Invoke-RestMethod http://localhost:5000/api/auth/register -Method Post -ContentType 'application/json' -Body '{"email":"admin@company.test","password":"change-this-immediately","firstName":"Admin","lastName":"User"}'
```

The first account becomes `super_admin`. Use it to sign in and create further accounts.

## MySQL setup

Create a MySQL database/user, then set this in `backend/.env`:

```dotenv
DATABASE_URL=mysql+mysqlconnector://smartattend:replace-this@localhost:3306/smartattend
SECRET_KEY=use-a-long-random-value
JWT_SECRET_KEY=use-a-different-long-random-value
CORS_ORIGINS=http://localhost:5173
```

Run [schema.sql](../database/schema.sql) for manual provisioning, or let SQLAlchemy initialize an empty database on first API startup. Then run `python backend/seed.py` to add only reference data.

## Biometric setup and privacy

The API runs with biometric recognition disabled by default. To activate it, install the optional runtime and configure a valid Fernet key:

```powershell
python -m pip install -r backend\requirements-biometrics.txt
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Set `FACE_RECOGNITION_ENABLED=true` and the generated `BIOMETRIC_ENCRYPTION_KEY` in `backend/.env`, then restart the API. `face-recognition` includes dlib and can need Windows C++ Build Tools depending on the available wheel.

Before production, conduct a local legal/privacy review, obtain clear consent, publish retention/deletion terms, restrict HR access, rotate encryption keys, and replace basic liveness detection with a tested anti-spoofing system. Biometric verification should not be the sole path to attendance—SmartAttend’s authorized manual flow remains available.

## Tests and production checks

```powershell
Set-Location backend
python -m pytest tests -q
Set-Location ..\frontend
npm run build
```

The test suite covers bootstrap RBAC, employee creation, attendance policy calculation, CSV export, employee data isolation, and leave approval/balance deduction.

For deployment, run Flask behind a production WSGI server/reverse proxy, force HTTPS, use MySQL backups/migrations, set real secrets and upload storage, configure email delivery for password resets, rate-limit authentication endpoints, and use a managed biometric/anti-spoofing provider where required.
