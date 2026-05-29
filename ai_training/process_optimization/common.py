import csv
import json
from pathlib import Path

import numpy as np


CONTEXT_FEATURES = ["material_moisture", "material_grade", "ambient_temp", "target_quality"]
CONTROL_FEATURES = ["set_temperature", "set_pressure", "set_flow_rate", "line_speed"]
FEATURES = CONTEXT_FEATURES + CONTROL_FEATURES
TARGETS = ["quality_score", "energy_consumption", "defect_rate"]


def read_csv(path):
    with Path(path).open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path, fieldnames, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def save_json(path, payload):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def matrix(rows, columns):
    return np.asarray([[float(row[col]) for col in columns] for row in rows], dtype=np.float32)


def make_design_matrix(x):
    parts = [np.ones((len(x), 1), dtype=np.float32), x]
    parts.append(x * x)
    interactions = []
    for i in range(x.shape[1]):
        for j in range(i + 1, x.shape[1]):
            interactions.append((x[:, i] * x[:, j])[:, None])
    if interactions:
        parts.extend(interactions)
    return np.concatenate(parts, axis=1)


def fit_regression(x, y, l2=1e-4):
    design = make_design_matrix(x)
    eye = np.eye(design.shape[1], dtype=np.float32) * l2
    eye[0, 0] = 0.0
    weights = np.linalg.solve(design.T @ design + eye, design.T @ y)
    pred = design @ weights
    mae = float(np.abs(pred - y).mean())
    rmse = float(np.sqrt(((pred - y) ** 2).mean()))
    return weights.astype(np.float32), {"mae": mae, "rmse": rmse}


def predict_regression(x, weights):
    return make_design_matrix(x) @ weights
