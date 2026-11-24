from datetime import date, datetime

from flask import jsonify, request


def payload(required=()):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, (jsonify({"error": "A JSON request body is required."}), 400)
    missing = [key for key in required if not data.get(key)]
    if missing:
        return None, (jsonify({"error": f"Missing required fields: {', '.join(missing)}."}), 400)
    return data, None


def parse_date(value, field_name="date"):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be ISO formatted (YYYY-MM-DD).")


def parse_datetime(value, field_name="timestamp"):
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except (AttributeError, ValueError):
        raise ValueError(f"{field_name} must be an ISO timestamp.")
