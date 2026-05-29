import argparse
from pathlib import Path

import numpy as np

from common import FEATURES, TARGETS, fit_regression, matrix, read_csv, save_json


def main():
    parser = argparse.ArgumentParser(description="Train process quality and energy models.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    rows = read_csv(args.data)
    x = matrix(rows, FEATURES)
    mean = x.mean(axis=0)
    std = x.std(axis=0) + 1e-6
    x_norm = (x - mean) / std

    models = {}
    metrics = {}
    for target in TARGETS:
        y = matrix(rows, [target]).reshape(-1)
        weights, target_metrics = fit_regression(x_norm, y)
        models[target] = weights.tolist()
        metrics[target] = target_metrics

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    save_json(
        output / "model.json",
        {
            "type": "polynomial_process_regression",
            "features": FEATURES,
            "targets": TARGETS,
            "mean": mean.tolist(),
            "std": std.tolist(),
            "models": models,
        },
    )
    save_json(output / "metrics.json", metrics)
    print(metrics)


if __name__ == "__main__":
    main()
