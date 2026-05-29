import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from common import load_json


def get_font(size=14):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def scale(value, low, high, size):
    if high <= low:
        return 0
    return (value - low) / (high - low) * size


def draw_bar(draw, x, base_y, width, height, color, label, value, font):
    y = base_y - height
    draw.rectangle((x, y, x + width, base_y), fill=color)
    draw.text((x - 4, y - 18), f"{value:.2f}", fill=(45, 45, 45), font=font)
    draw.text((x - 5, base_y + 8), label, fill=(70, 70, 70), font=font)


def main():
    parser = argparse.ArgumentParser(description="Plot process optimization candidate comparison.")
    parser.add_argument("--recommendation", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--top-n", type=int, default=6)
    args = parser.parse_args()

    payload = load_json(args.recommendation)
    candidates = payload["top_candidates"][: args.top_n]
    if not candidates:
        raise SystemExit("No candidates found.")

    quality_values = [c["prediction"]["quality_score"] for c in candidates]
    energy_values = [c["prediction"]["energy_consumption"] for c in candidates]
    defect_values = [c["prediction"]["defect_rate"] for c in candidates]
    target_quality = payload["context"]["target_quality"]

    width, height = 1180, 620
    image = Image.new("RGB", (width, height), (248, 248, 245))
    draw = ImageDraw.Draw(image)
    title_font = get_font(24)
    font = get_font(13)
    small_font = get_font(12)

    draw.text((54, 28), "Process Parameter Candidate Comparison", fill=(25, 25, 25), font=title_font)
    context = payload["context"]
    context_text = (
        f"moisture={context['material_moisture']}  grade={context['material_grade']}  "
        f"ambient={context['ambient_temp']}  target_quality={target_quality}"
    )
    draw.text((54, 62), context_text, fill=(75, 75, 75), font=font)

    chart_left, chart_top = 70, 126
    chart_bottom = 500
    group_width = 170
    bar_width = 34
    gap = 8

    quality_low = min(min(quality_values), target_quality) - 2
    quality_high = max(max(quality_values), target_quality) + 2
    energy_low = min(energy_values) - 3
    energy_high = max(energy_values) + 3
    defect_low = 0.0
    defect_high = max(defect_values) * 1.25 + 0.001

    draw.line((chart_left, chart_bottom, width - 52, chart_bottom), fill=(180, 180, 175), width=1)

    colors = {
        "quality": (35, 105, 190),
        "energy": (45, 150, 95),
        "defect": (230, 145, 45),
    }
    legend = [
        ("quality score", colors["quality"]),
        ("energy consumption", colors["energy"]),
        ("defect rate x100", colors["defect"]),
        ("* recommended", (220, 70, 55)),
    ]
    legend_x = 54
    for label, color in legend:
        draw.rectangle((legend_x, 92, legend_x + 16, 108), fill=color)
        draw.text((legend_x + 22, 91), label, fill=(70, 70, 70), font=font)
        legend_x += 190

    for i, candidate in enumerate(candidates):
        x0 = chart_left + i * group_width
        pred = candidate["prediction"]
        controls = candidate["controls"]

        q_height = scale(pred["quality_score"], quality_low, quality_high, 240)
        e_height = scale(pred["energy_consumption"], energy_low, energy_high, 240)
        d_height = scale(pred["defect_rate"], defect_low, defect_high, 240)

        if i == 0:
            draw.text((x0 + 35, chart_top - 24), "*", fill=(220, 70, 55), font=title_font)

        draw_bar(draw, x0, chart_bottom, bar_width, q_height, colors["quality"], "Q", pred["quality_score"], small_font)
        draw_bar(draw, x0 + bar_width + gap, chart_bottom, bar_width, e_height, colors["energy"], "E", pred["energy_consumption"], small_font)
        draw_bar(draw, x0 + (bar_width + gap) * 2, chart_bottom, bar_width, d_height, colors["defect"], "D", pred["defect_rate"] * 100, small_font)

        draw.text((x0 - 4, chart_bottom + 34), f"#{i + 1} score={candidate['score']:.2f}", fill=(45, 45, 45), font=small_font)
        params = (
            f"T {controls['set_temperature']:.1f}\n"
            f"P {controls['set_pressure']:.3f}\n"
            f"F {controls['set_flow_rate']:.1f}\n"
            f"S {controls['line_speed']:.1f}"
        )
        draw.multiline_text((x0 - 4, chart_bottom + 54), params, fill=(75, 75, 75), font=small_font, spacing=2)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, quality=95)
    print(f"saved candidate comparison chart to {output}")


if __name__ == "__main__":
    main()
