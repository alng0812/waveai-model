import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image


def softmax(logits):
    logits = logits - logits.max(axis=1, keepdims=True)
    exp = np.exp(logits)
    return exp / exp.sum(axis=1, keepdims=True)


def image_to_features(path, image_size):
    image = Image.open(path).convert("RGB").resize((image_size, image_size))
    arr = np.asarray(image, dtype=np.float32) / 255.0
    mean = arr.mean(axis=(0, 1))
    std = arr.std(axis=(0, 1))
    half = image_size // 2
    quadrants = [
        arr[:half, :half].mean(axis=(0, 1)),
        arr[:half, half:].mean(axis=(0, 1)),
        arr[half:, :half].mean(axis=(0, 1)),
        arr[half:, half:].mean(axis=(0, 1)),
    ]
    return np.concatenate([mean, std, *quadrants]).astype(np.float32)


def main():
    parser = argparse.ArgumentParser(description="Run prediction with the lightweight classifier.")
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()

    model_dir = Path(args.model_dir)
    data = np.load(model_dir / "model.npz")
    labels = json.loads((model_dir / "labels.json").read_text(encoding="utf-8"))["classes"]

    image_size = int(data["image_size"][0])
    features = image_to_features(Path(args.image), image_size)[None, :]
    features = (features - data["feature_mean"]) / data["feature_std"]

    probs = softmax(features @ data["weights"] + data["bias"])[0]
    index = int(probs.argmax())
    result = {
        "label": labels[index],
        "confidence": float(probs[index]),
        "probabilities": {label: float(probs[i]) for i, label in enumerate(labels)},
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
