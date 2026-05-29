import argparse
import random
from pathlib import Path

import numpy as np

from common import CONTROL_FEATURES, FEATURES, load_json, predict_regression, save_json


RANGES = {
    "set_temperature": (118.0, 158.0),
    "set_pressure": (0.65, 1.05),
    "set_flow_rate": (34.0, 62.0),
    "line_speed": (52.0, 96.0),
}


def build_row(context, controls):
    return np.asarray([[context[name] if name in context else controls[name] for name in FEATURES]], dtype=np.float32)


def predict(model, context, controls):
    x = build_row(context, controls)
    mean = np.asarray(model["mean"], dtype=np.float32)
    std = np.asarray(model["std"], dtype=np.float32)
    x = (x - mean) / std
    result = {}
    for target, weights in model["models"].items():
        result[target] = float(predict_regression(x, np.asarray(weights, dtype=np.float32))[0])
    result["defect_rate"] = max(0.0, min(1.0, result["defect_rate"]))
    return result


def sample_controls(rng):
    return {name: rng.uniform(low, high) for name, (low, high) in RANGES.items()}


def score_candidate(pred, target_quality, quality_weight, energy_weight, defect_weight):
    quality_gap = max(0.0, target_quality - pred["quality_score"])
    quality_bonus = max(0.0, pred["quality_score"] - target_quality) * 0.08
    return (
        quality_gap * quality_weight
        + pred["energy_consumption"] * energy_weight
        + pred["defect_rate"] * defect_weight
        - quality_bonus
    )


def main():
    parser = argparse.ArgumentParser(description="Recommend process parameters.")
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--material-moisture", type=float, required=True)
    parser.add_argument("--material-grade", type=float, required=True)
    parser.add_argument("--ambient-temp", type=float, required=True)
    parser.add_argument("--target-quality", type=float, required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--candidates", type=int, default=8000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--quality-weight", type=float, default=8.0)
    parser.add_argument("--energy-weight", type=float, default=0.08)
    parser.add_argument("--defect-weight", type=float, default=180.0)
    args = parser.parse_args()

    model = load_json(Path(args.model_dir) / "model.json")
    context = {
        "material_moisture": args.material_moisture,
        "material_grade": args.material_grade,
        "ambient_temp": args.ambient_temp,
        "target_quality": args.target_quality,
    }
    rng = random.Random(args.seed)

    ranked = []
    for _ in range(args.candidates):
        controls = sample_controls(rng)
        pred = predict(model, context, controls)
        score = score_candidate(pred, args.target_quality, args.quality_weight, args.energy_weight, args.defect_weight)
        ranked.append((score, controls, pred))
    ranked.sort(key=lambda item: item[0])

    top = []
    for score, controls, pred in ranked[:10]:
        top.append(
            {
                "score": score,
                "controls": {name: round(value, 4) for name, value in controls.items()},
                "prediction": {name: round(value, 5) for name, value in pred.items()},
            }
        )

    payload = {
        "context": context,
        "recommendation": top[0],
        "top_candidates": top,
        "control_ranges": RANGES,
    }
    save_json(args.output, payload)
    print(payload["recommendation"])


if __name__ == "__main__":
    main()
