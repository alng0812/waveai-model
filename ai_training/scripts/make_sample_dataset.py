import argparse
import random
from pathlib import Path

from PIL import Image, ImageDraw


def draw_circle(path, size, rng):
    image = Image.new("RGB", (size, size), (245, 245, 245))
    draw = ImageDraw.Draw(image)
    margin = rng.randint(8, 18)
    color = (rng.randint(190, 240), rng.randint(40, 80), rng.randint(40, 80))
    draw.ellipse((margin, margin, size - margin, size - margin), fill=color)
    image.save(path)


def draw_square(path, size, rng):
    image = Image.new("RGB", (size, size), (245, 245, 245))
    draw = ImageDraw.Draw(image)
    margin = rng.randint(8, 18)
    color = (rng.randint(40, 80), rng.randint(90, 160), rng.randint(190, 240))
    draw.rectangle((margin, margin, size - margin, size - margin), fill=color)
    image.save(path)


def main():
    parser = argparse.ArgumentParser(description="Create a tiny sample image dataset.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--size", type=int, default=64)
    parser.add_argument("--train-count", type=int, default=50)
    parser.add_argument("--val-count", type=int, default=12)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    output = Path(args.output)
    specs = [
        ("circle", draw_circle),
        ("square", draw_square),
    ]

    for split, count in [("train", args.train_count), ("val", args.val_count)]:
        for class_name, drawer in specs:
            class_dir = output / split / class_name
            class_dir.mkdir(parents=True, exist_ok=True)
            for i in range(count):
                drawer(class_dir / f"{i:04d}.png", args.size, rng)

    print(f"sample dataset saved to {output}")


if __name__ == "__main__":
    main()
