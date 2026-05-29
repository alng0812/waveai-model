import argparse
import random
from pathlib import Path

from PIL import Image, ImageDraw


CLASSES = ["scratch", "stain", "crack", "chip"]


def write_yaml(path, root):
    names = "\n".join(f"  {i}: {name}" for i, name in enumerate(CLASSES))
    text = f"""path: .
train: images/train
val: images/val
names:
{names}
"""
    path.write_text(text, encoding="utf-8")


def add_texture(draw, size, rng):
    for _ in range(12):
        color = rng.randint(214, 238)
        x1 = rng.randint(0, size)
        y1 = rng.randint(0, size)
        x2 = min(size, x1 + rng.randint(20, 90))
        y2 = min(size, y1 + rng.randint(1, 3))
        draw.rectangle((x1, y1, x2, y2), fill=(color, color, color))


def add_label(labels, class_id, x1, y1, x2, y2, size):
    x1 = max(0, min(size - 1, x1))
    y1 = max(0, min(size - 1, y1))
    x2 = max(x1 + 1, min(size, x2))
    y2 = max(y1 + 1, min(size, y2))
    x_center = ((x1 + x2) / 2) / size
    y_center = ((y1 + y2) / 2) / size
    width = (x2 - x1) / size
    height = (y2 - y1) / size
    labels.append(f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}")


def draw_scratch(draw, labels, size, rng):
    x1 = rng.randint(20, size - 90)
    y1 = rng.randint(20, size - 40)
    length = rng.randint(55, 120)
    rise = rng.randint(-20, 20)
    width = rng.randint(3, 7)
    x2 = min(size - 12, x1 + length)
    y2 = max(12, min(size - 12, y1 + rise))
    draw.line((x1, y1, x2, y2), fill=(60, 60, 60), width=width)
    pad = width + 3
    add_label(labels, 0, min(x1, x2) - pad, min(y1, y2) - pad, max(x1, x2) + pad, max(y1, y2) + pad, size)


def draw_stain(draw, labels, size, rng):
    cx = rng.randint(35, size - 35)
    cy = rng.randint(35, size - 35)
    rx = rng.randint(12, 36)
    ry = rng.randint(10, 30)
    color = (rng.randint(95, 150), rng.randint(75, 120), rng.randint(45, 85))
    draw.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=color)
    add_label(labels, 1, cx - rx, cy - ry, cx + rx, cy + ry, size)


def draw_crack(draw, labels, size, rng):
    points = []
    x = rng.randint(25, size - 80)
    y = rng.randint(25, size - 40)
    points.append((x, y))
    for _ in range(rng.randint(3, 5)):
        x += rng.randint(14, 34)
        y += rng.randint(-18, 18)
        x = min(size - 15, x)
        y = max(15, min(size - 15, y))
        points.append((x, y))
    draw.line(points, fill=(25, 25, 25), width=rng.randint(2, 4))
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    add_label(labels, 2, min(xs) - 5, min(ys) - 5, max(xs) + 5, max(ys) + 5, size)


def draw_chip(draw, labels, size, rng):
    x1 = rng.randint(25, size - 70)
    y1 = rng.randint(25, size - 70)
    w = rng.randint(24, 55)
    h = rng.randint(18, 45)
    points = [
        (x1, y1 + rng.randint(3, h // 2)),
        (x1 + rng.randint(w // 3, w), y1),
        (x1 + w, y1 + rng.randint(h // 3, h)),
        (x1 + rng.randint(0, w // 2), y1 + h),
    ]
    draw.polygon(points, fill=(238, 238, 224), outline=(90, 90, 80))
    add_label(labels, 3, x1, y1, x1 + w, y1 + h, size)


def draw_sample(image_path, label_path, size, rng):
    base = rng.randint(224, 244)
    image = Image.new("RGB", (size, size), (base, base, base - rng.randint(0, 8)))
    draw = ImageDraw.Draw(image)
    labels = []
    add_texture(draw, size, rng)

    drawers = [draw_scratch, draw_stain, draw_crack, draw_chip]
    object_count = rng.randint(1, 4)
    for _ in range(object_count):
        rng.choice(drawers)(draw, labels, size, rng)

    image.save(image_path)
    label_path.write_text("\n".join(labels) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Create a synthetic YOLO detection dataset.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--size", type=int, default=320)
    parser.add_argument("--train-count", type=int, default=80)
    parser.add_argument("--val-count", type=int, default=20)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    root = Path(args.output).resolve()

    for split, count in [("train", args.train_count), ("val", args.val_count)]:
        image_dir = root / "images" / split
        label_dir = root / "labels" / split
        image_dir.mkdir(parents=True, exist_ok=True)
        label_dir.mkdir(parents=True, exist_ok=True)

        for i in range(count):
            stem = f"{i:05d}"
            draw_sample(image_dir / f"{stem}.jpg", label_dir / f"{stem}.txt", args.size, rng)

    write_yaml(root / "dataset.yaml", root)
    print(f"synthetic detection dataset saved to {root}")


if __name__ == "__main__":
    main()
