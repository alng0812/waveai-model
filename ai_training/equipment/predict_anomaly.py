import argparse

import numpy as np

from common import feature_matrix, load_json, read_csv, write_csv
from train_anomaly_detector import anomaly_scores


def main():
    parser = argparse.ArgumentParser(description="Predict equipment anomalies.")
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--data", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    model = load_json(f"{args.model_dir}/model.json")
    rows = read_csv(args.data)
    x = feature_matrix(rows, model["features"])
    mean = np.asarray(model["mean"], dtype=np.float32)
    std = np.asarray(model["std"], dtype=np.float32)
    scores = anomaly_scores(x, mean, std)
    pred = (scores >= float(model["threshold"])).astype(int)

    out_rows = []
    for row, score, label in zip(rows, scores, pred):
        out = dict(row)
        out["anomaly_score"] = f"{float(score):.6f}"
        out["predicted_anomaly"] = int(label)
        out_rows.append(out)

    write_csv(args.output, list(out_rows[0].keys()), out_rows)
    print(f"saved predictions to {args.output}")


if __name__ == "__main__":
    main()
