import argparse
from pathlib import Path

import numpy as np

from common import FEATURES, binary_metrics, feature_matrix, int_labels, read_csv, save_json


def anomaly_scores(x, mean, std):
    z = np.abs((x - mean) / std)
    return z.mean(axis=1) + z.max(axis=1) * 0.35


def main():
    parser = argparse.ArgumentParser(description="Train a simple equipment anomaly detector.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--threshold-percentile", type=float, default=99.0)
    args = parser.parse_args()

    rows = read_csv(args.data)
    x = feature_matrix(rows)
    y = int_labels(rows, "anomaly")

    normal_x = x[y == 0]
    if len(normal_x) < 10:
        raise SystemExit("Need at least 10 normal rows to train anomaly detector.")

    mean = normal_x.mean(axis=0)
    std = normal_x.std(axis=0) + 1e-6
    normal_scores = anomaly_scores(normal_x, mean, std)
    threshold = float(np.percentile(normal_scores, args.threshold_percentile))

    scores = anomaly_scores(x, mean, std)
    pred = (scores >= threshold).astype(np.int64)
    metrics = binary_metrics(y, pred)

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    save_json(
        output / "model.json",
        {
            "type": "zscore_anomaly_detector",
            "features": FEATURES,
            "mean": mean.tolist(),
            "std": std.tolist(),
            "threshold": threshold,
            "threshold_percentile": args.threshold_percentile,
        },
    )
    save_json(output / "metrics.json", metrics)
    print(metrics)


if __name__ == "__main__":
    main()
