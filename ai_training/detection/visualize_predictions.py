import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


COLORS = {
    "scratch": (235, 90, 35),
    "stain": (140, 95, 45),
    "crack": (35, 35, 35),
    "chip": (30, 120, 210),
}
DEFAULT_COLOR = (40, 180, 100)


def get_font(size=14):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def draw_detection(draw, detection, font):
    label = detection["label"]
    confidence = detection["confidence"]
    x1, y1, x2, y2 = detection["box_xyxy"]
    color = COLORS.get(label, DEFAULT_COLOR)

    draw.rectangle((x1, y1, x2, y2), outline=color, width=3)
    confidence_text = f"{confidence:.3f}" if confidence < 0.1 else f"{confidence:.2f}"
    text = f"{label} {confidence_text}"
    bbox = draw.textbbox((x1, y1), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    label_y = max(0, y1 - text_h - 6)
    draw.rectangle((x1, label_y, x1 + text_w + 8, label_y + text_h + 6), fill=color)
    draw.text((x1 + 4, label_y + 3), text, fill=(255, 255, 255), font=font)


def main():
    parser = argparse.ArgumentParser(description="Draw YOLO predictions on images.")
    parser.add_argument("--predictions", required=True, help="Path to prediction JSON.")
    parser.add_argument("--output-dir", required=True, help="Directory for annotated images.")
    parser.add_argument("--min-conf", type=float, default=0.25)
    args = parser.parse_args()

    predictions = json.loads(Path(args.predictions).read_text(encoding="utf-8"))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    font = get_font()

    written = []
    for item in predictions:
        image_path = Path(item["image"])
        image = Image.open(image_path).convert("RGB")
        draw = ImageDraw.Draw(image)

        kept = [
            detection
            for detection in item.get("detections", [])
            if detection.get("confidence", 0.0) >= args.min_conf
        ]
        for detection in kept:
            draw_detection(draw, detection, font)

        output_path = output_dir / f"{image_path.stem}_annotated.jpg"
        image.save(output_path, quality=95)
        written.append({"image": str(image_path), "output": str(output_path), "detections": len(kept)})

    print(json.dumps(written, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
