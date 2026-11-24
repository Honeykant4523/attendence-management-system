"""Train a transparent late-arrival risk model from exported attendance history.

Usage: python ml_models/attendance_prediction.py attendance.csv
The input needs employee_id, date, late_minutes and status columns.
"""
import sys
from pathlib import Path

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split


def train(csv_path: str):
    frame = pd.read_csv(csv_path, parse_dates=["date"])
    required = {"employee_id", "date", "late_minutes", "status"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Missing columns: {', '.join(sorted(missing))}")
    frame["weekday"] = frame["date"].dt.weekday
    frame["month"] = frame["date"].dt.month
    frame["was_late"] = (frame["late_minutes"] > 0).astype(int)
    features = frame[["employee_id", "weekday", "month"]]
    target = frame["was_late"]
    if target.nunique() < 2 or len(frame) < 20:
        raise ValueError("At least 20 records containing late and non-late examples are required.")
    x_train, x_test, y_train, y_test = train_test_split(features, target, test_size=0.25, random_state=42, stratify=target)
    model = RandomForestClassifier(n_estimators=150, random_state=42, class_weight="balanced")
    model.fit(x_train, y_train)
    print(f"Validation accuracy: {model.score(x_test, y_test):.2%}")
    print("Feature importance:", dict(zip(features.columns, model.feature_importances_.round(3))))
    return model


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python attendance_prediction.py attendance.csv")
    train(sys.argv[1])
