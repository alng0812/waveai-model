import argparse
import json
import math
import random
from pathlib import Path

import numpy as np
from PIL import Image


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def log(message, log_file):
    print(message)
    with log_file.open("a", encoding="utf-8") as f:
        f.write(message + "\n")


def list_images(root):
    samples = []
    classes = sorted([p.name for p in root.iterdir() if p.is_dir()])
    for class_index, class_name in enumerate(classes):
        class_dir = root / class_name
        for path in sorted(class_dir.rglob("*")):
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
                samples.append((path, class_index))
    return classes, samples


def split_train_val(train_samples, val_ratio, seed):
    rng = random.Random(seed)
    by_class = {}
    for path, label in train_samples:
        by_class.setdefault(label, []).append((path, label))

    train, val = [], []
    for label_samples in by_class.values():
        rng.shuffle(label_samples)
        val_count = max(1, int(round(len(label_samples) * val_ratio))) if len(label_samples) > 1 else 0
        val.extend(label_samples[:val_count])
        train.extend(label_samples[val_count:])

    rng.shuffle(train)
    rng.shuffle(val)
    return train, val


def image_to_features(path, image_size):
    image = Image.open(path).convert("RGB").resize((image_size, image_size))
    arr = np.asarray(image, dtype=np.float32) / 255.0

    mean = arr.mean(axis=(0, 1))
    std = arr.std(axis=(0, 1))

    # Add a small spatial signal so simple shapes/colors can be learned.
    half = image_size // 2
    quadrants = [
        arr[:half, :half].mean(axis=(0, 1)),
        arr[:half, half:].mean(axis=(0, 1)),
        arr[half:, :half].mean(axis=(0, 1)),
        arr[half:, half:].mean(axis=(0, 1)),
    ]
    features = np.concatenate([mean, std, *quadrants])
    return features.astype(np.float32)


def load_matrix(samples, image_size):
    x = np.stack([image_to_features(path, image_size) for path, _ in samples])
    y = np.asarray([label for _, label in samples], dtype=np.int64)
    return x, y


def standardize(train_x, val_x):
    mean = train_x.mean(axis=0, keepdims=True)
    std = train_x.std(axis=0, keepdims=True) + 1e-6
    return (train_x - mean) / std, (val_x - mean) / std, mean, std


def softmax(logits):
    logits = logits - logits.max(axis=1, keepdims=True)
    exp = np.exp(logits)
    return exp / exp.sum(axis=1, keepdims=True)


def evaluate(x, y, weights, bias):
    probs = softmax(x @ weights + bias)
    predictions = probs.argmax(axis=1)
    accuracy = float((predictions == y).mean()) if len(y) else 0.0
    loss = cross_entropy(probs, y)
    return accuracy, loss


def cross_entropy(probs, y):
    clipped = np.clip(probs[np.arange(len(y)), y], 1e-8, 1.0)
    return float(-np.log(clipped).mean())


def train(train_x, train_y, val_x, val_y, class_count, epochs, lr, batch_size, seed, log_file):
    rng = np.random.default_rng(seed)
    feature_count = train_x.shape[1]
    weights = rng.normal(0, 0.01, size=(feature_count, class_count)).astype(np.float32)
    bias = np.zeros((1, class_count), dtype=np.float32)

    for epoch in range(1, epochs + 1):
        order = rng.permutation(len(train_x))
        batch_losses = []

        for start in range(0, len(order), batch_size):
            batch_indices = order[start : start + batch_size]
            x_batch = train_x[batch_indices]
            y_batch = train_y[batch_indices]

            probs = softmax(x_batch @ weights + bias)
            batch_losses.append(cross_entropy(probs, y_batch))

            grad_logits = probs
            grad_logits[np.arange(len(y_batch)), y_batch] -= 1.0
            grad_logits /= len(y_batch)

            grad_w = x_batch.T @ grad_logits
            grad_b = grad_logits.sum(axis=0, keepdims=True)

            weights -= lr * grad_w
            bias -= lr * grad_b

        train_acc, train_loss = evaluate(train_x, train_y, weights, bias)
        val_acc, val_loss = evaluate(val_x, val_y, weights, bias) if len(val_y) else (0.0, math.nan)
        log(
            f"epoch={epoch:03d} train_loss={train_loss:.4f} train_acc={train_acc:.4f} "
            f"val_loss={val_loss:.4f} val_acc={val_acc:.4f}",
            log_file,
        )

    return weights, bias


def main():
    parser = argparse.ArgumentParser(description="Train a lightweight image classifier.")
    parser.add_argument("--dataset", required=True, help="Dataset root with train/ and optional val/.")
    parser.add_argument("--output", required=True, help="Output directory for model artifacts.")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--lr", type=float, default=0.1)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--image-size", type=int, default=64)
    parser.add_argument("--val-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    dataset = Path(args.dataset)
    output = Path(args.output)
    train_root = dataset / "train"
    val_root = dataset / "val"
    output.mkdir(parents=True, exist_ok=True)
    log_file = output / "train.log"
    log_file.write_text("", encoding="utf-8")

    if not train_root.exists():
        raise SystemExit(f"Missing train directory: {train_root}")

    classes, train_samples = list_images(train_root)
    if len(classes) < 2:
        raise SystemExit("At least two classes are required.")
    if not train_samples:
        raise SystemExit("No training images found.")

    if val_root.exists():
        val_classes, val_samples = list_images(val_root)
        if val_classes != classes:
            raise SystemExit("train/ and val/ class names must match.")
    else:
        train_samples, val_samples = split_train_val(train_samples, args.val_ratio, args.seed)

    if not train_samples:
        raise SystemExit("Training split is empty.")

    log(f"classes={classes}", log_file)
    log(f"train_samples={len(train_samples)} val_samples={len(val_samples)}", log_file)

    train_x, train_y = load_matrix(train_samples, args.image_size)
    val_x, val_y = load_matrix(val_samples, args.image_size) if val_samples else (
        np.empty((0, train_x.shape[1]), dtype=np.float32),
        np.empty((0,), dtype=np.int64),
    )
    train_x, val_x, feature_mean, feature_std = standardize(train_x, val_x)

    weights, bias = train(
        train_x,
        train_y,
        val_x,
        val_y,
        len(classes),
        args.epochs,
        args.lr,
        args.batch_size,
        args.seed,
        log_file,
    )

    train_acc, train_loss = evaluate(train_x, train_y, weights, bias)
    val_acc, val_loss = evaluate(val_x, val_y, weights, bias) if len(val_y) else (0.0, math.nan)

    np.savez(
        output / "model.npz",
        weights=weights,
        bias=bias,
        feature_mean=feature_mean,
        feature_std=feature_std,
        image_size=np.asarray([args.image_size], dtype=np.int64),
    )

    (output / "labels.json").write_text(
        json.dumps({"classes": classes}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    metrics = {
        "train_accuracy": train_acc,
        "train_loss": train_loss,
        "val_accuracy": val_acc,
        "val_loss": val_loss,
        "epochs": args.epochs,
        "train_samples": len(train_samples),
        "val_samples": len(val_samples),
    }
    (output / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log(f"saved_model={output / 'model.npz'}", log_file)
    log(f"metrics={metrics}", log_file)


if __name__ == "__main__":
    main()
