import argparse

import numpy as np

from common import feature_matrix, load_json, read_csv, write_csv
from train_fault_predictor import sigmoid


def main():
    parser = argparse.ArgumentParser(description="Predict equipment fault risk.")
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--data", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    model = load_json(f"{args.model_dir}/model.json")
    rows = read_csv(args.data)
    x = feature_matrix(rows, model["features"])
    mean = np.asarray(model["mean"], dtype=np.float32)
    std = np.asarray(model["std"], dtype=np.float32)
    weights = np.asarray(model["weights"], dtype=np.float32)
    bias = float(model["bias"])

    x = (x - mean) / std
    risks = sigmoid(x @ weights + bias)
    pred = (risks >= float(model["threshold"])).astype(int)

    out_rows = []
    for row, risk, label in zip(rows, risks, pred):
        out = dict(row)
        out["fault_risk"] = f"{float(risk):.6f}"
        out["predicted_fault"] = int(label)
        out_rows.append(out)

    write_csv(args.output, list(out_rows[0].keys()), out_rows)
    print(f"saved predictions to {args.output}")


if __name__ == "__main__":
    main()
