"""Detect unusual attendance patterns without treating them as disciplinary facts."""
import sys

import pandas as pd
from sklearn.ensemble import IsolationForest


def detect(csv_path: str):
    frame = pd.read_csv(csv_path)
    features = frame[["late_minutes", "work_minutes", "overtime_minutes"]].fillna(0)
    if len(features) < 20:
        raise ValueError("At least 20 attendance records are required for anomaly detection.")
    model = IsolationForest(contamination=0.08, random_state=42)
    frame["anomaly"] = model.fit_predict(features) == -1
    return frame[frame["anomaly"]]


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python anomaly_detection.py attendance.csv")
    print(detect(sys.argv[1]).to_string(index=False))
