import argparse
from pathlib import Path

import numpy as np

from common import FEATURES, binary_metrics, feature_matrix, int_labels, read_csv, save_json


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -30, 30)))


def main():
    parser = argparse.ArgumentParser(description="Train a simple equipment fault risk predictor.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--epochs", type=int, default=300)
    parser.add_argument("--lr", type=float, default=0.08)
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args()

    rows = read_csv(args.data)
    x = feature_matrix(rows)
    y = int_labels(rows, "fault_within_24h").astype(np.float32)

    mean = x.mean(axis=0)
    std = x.std(axis=0) + 1e-6
    x = (x - mean) / std

    rng = np.random.default_rng(42)
    weights = rng.normal(0, 0.01, size=x.shape[1]).astype(np.float32)
    bias = np.float32(0.0)
    pos_weight = float((len(y) - y.sum()) / max(1.0, y.sum()))

    for _ in range(args.epochs):
        logits = x @ weights + bias
        probs = sigmoid(logits)
        weights_per_row = np.where(y == 1, pos_weight, 1.0)
        error = (probs - y) * weights_per_row
        weights -= args.lr * (x.T @ error / len(x))
        bias -= args.lr * error.mean()

    probs = sigmoid(x @ weights + bias)
    pred = (probs >= args.threshold).astype(np.int64)
    metrics = binary_metrics(y.astype(np.int64), pred)

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    save_json(
        output / "model.json",
        {
            "type": "logistic_fault_predictor",
            "features": FEATURES,
            "mean": mean.tolist(),
            "std": std.tolist(),
            "weights": weights.tolist(),
            "bias": float(bias),
            "threshold": args.threshold,
        },
    )
    save_json(output / "metrics.json", metrics)
    print(metrics)


if __name__ == "__main__":
    main()
