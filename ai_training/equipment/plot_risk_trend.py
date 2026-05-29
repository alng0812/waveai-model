import argparse
import csv
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def read_rows(path, equipment_id):
    with Path(path).open("r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    rows = [row for row in rows if row["equipment_id"] == equipment_id]
    rows.sort(key=lambda row: row["timestamp"])
    return rows


def font(size=14):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def scale(value, src_min, src_max, dst_min, dst_max):
    if src_max == src_min:
        return (dst_min + dst_max) / 2
    return dst_min + (value - src_min) / (src_max - src_min) * (dst_max - dst_min)


def draw_polyline(draw, points, color, width=2):
    if len(points) >= 2:
        draw.line(points, fill=color, width=width, joint="curve")


def main():
    parser = argparse.ArgumentParser(description="Plot equipment fault risk trend.")
    parser.add_argument("--predictions", required=True, help="CSV from predict_fault.py.")
    parser.add_argument("--equipment-id", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-points", type=int, default=240)
    args = parser.parse_args()

    rows = read_rows(args.predictions, args.equipment_id)
    if not rows:
        raise SystemExit(f"No rows found for equipment_id={args.equipment_id}")
    rows = rows[-args.max_points :]

    risks = [float(row["fault_risk"]) for row in rows]
    anomalies = [int(row.get("predicted_anomaly", row.get("anomaly", 0))) for row in rows]
    faults = [int(row.get("predicted_fault", 0)) for row in rows]
    times = [datetime.strptime(row["timestamp"], "%Y-%m-%d %H:%M:%S") for row in rows]

    width, height = 1180, 520
    margin_left, margin_right = 74, 36
    margin_top, margin_bottom = 72, 74
    chart_left = margin_left
    chart_right = width - margin_right
    chart_top = margin_top
    chart_bottom = height - margin_bottom

    image = Image.new("RGB", (width, height), (248, 248, 245))
    draw = ImageDraw.Draw(image)
    title_font = font(24)
    label_font = font(14)
    small_font = font(12)

    draw.text((margin_left, 24), f"Equipment Fault Risk Trend - {args.equipment_id}", fill=(25, 25, 25), font=title_font)
    draw.rectangle((chart_left, chart_top, chart_right, chart_bottom), outline=(190, 190, 185), width=1)

    for tick in [0.0, 0.25, 0.5, 0.75, 1.0]:
        y = scale(tick, 0, 1, chart_bottom, chart_top)
        color = (220, 220, 216) if tick != 0.5 else (235, 120, 80)
        draw.line((chart_left, y, chart_right, y), fill=color, width=1)
        draw.text((18, y - 8), f"{tick:.2f}", fill=(90, 90, 90), font=small_font)

    points = []
    for i, risk in enumerate(risks):
        x = scale(i, 0, max(1, len(risks) - 1), chart_left, chart_right)
        y = scale(risk, 0, 1, chart_bottom, chart_top)
        points.append((x, y))
    draw_polyline(draw, points, (35, 105, 190), width=3)

    for i, (risk, is_anomaly, is_fault) in enumerate(zip(risks, anomalies, faults)):
        x, y = points[i]
        if is_fault:
            draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=(220, 55, 45))
        elif is_anomaly:
            draw.rectangle((x - 4, y - 4, x + 4, y + 4), fill=(235, 150, 35))

    start_label = times[0].strftime("%m-%d %H:%M")
    end_label = times[-1].strftime("%m-%d %H:%M")
    draw.text((chart_left, chart_bottom + 18), start_label, fill=(80, 80, 80), font=small_font)
    draw.text((chart_right - 86, chart_bottom + 18), end_label, fill=(80, 80, 80), font=small_font)
    draw.text((chart_left, height - 34), "blue: fault risk   orange: anomaly   red: predicted fault   red line: 0.50 threshold", fill=(70, 70, 70), font=label_font)

    max_risk = max(risks)
    avg_risk = sum(risks) / len(risks)
    summary = f"points={len(risks)}  max_risk={max_risk:.3f}  avg_risk={avg_risk:.3f}  predicted_faults={sum(faults)}"
    draw.text((chart_right - 430, 31), summary, fill=(70, 70, 70), font=small_font)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, quality=95)
    print(f"saved trend chart to {output}")


if __name__ == "__main__":
    main()
