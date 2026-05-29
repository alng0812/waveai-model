import argparse
import csv
import random
from pathlib import Path


HEADER = [
    "material_moisture",
    "material_grade",
    "ambient_temp",
    "target_quality",
    "set_temperature",
    "set_pressure",
    "set_flow_rate",
    "line_speed",
    "quality_score",
    "energy_consumption",
    "defect_rate",
]


def clamp(value, low, high):
    return max(low, min(high, value))


def simulate(row, rng):
    moisture = row["material_moisture"]
    grade = row["material_grade"]
    ambient = row["ambient_temp"]
    target = row["target_quality"]
    temp = row["set_temperature"]
    pressure = row["set_pressure"]
    flow = row["set_flow_rate"]
    speed = row["line_speed"]

    ideal_temp = 132 + moisture * 85 - grade * 3 + (target - 90) * 0.45
    ideal_pressure = 0.72 + moisture * 0.55 + grade * 0.035
    ideal_flow = 42 + grade * 4 + moisture * 35
    ideal_speed = 78 - moisture * 42 + grade * 3 - max(0, target - 92) * 0.8

    temp_error = abs(temp - ideal_temp) / 16
    pressure_error = abs(pressure - ideal_pressure) / 0.18
    flow_error = abs(flow - ideal_flow) / 14
    speed_error = abs(speed - ideal_speed) / 18

    stability_penalty = temp_error * 7 + pressure_error * 5 + flow_error * 4 + speed_error * 4
    heat_penalty = max(0, temp - ideal_temp - 10) * 0.12
    speed_penalty = max(0, speed - ideal_speed - 12) * 0.18

    quality = target + 5.5 - stability_penalty - heat_penalty - speed_penalty + rng.gauss(0, 0.8)
    quality = clamp(quality, 55, 99.5)

    energy = (
        82
        + (temp - 120) * 0.42
        + pressure * 18
        + flow * 0.23
        + speed * 0.16
        + max(0, ambient - 28) * 0.8
        + rng.gauss(0, 1.2)
    )
    energy = max(50, energy)

    defect = (100 - quality) / 100 + max(0, speed_error - 0.8) * 0.08 + rng.uniform(0, 0.01)
    defect = clamp(defect, 0.002, 0.35)
    return quality, energy, defect


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic process parameter data.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--rows", type=int, default=3000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for _ in range(args.rows):
        row = {
            "material_moisture": rng.uniform(0.08, 0.26),
            "material_grade": rng.choice([1, 2, 3]),
            "ambient_temp": rng.uniform(18, 35),
            "target_quality": rng.uniform(88, 96),
            "set_temperature": rng.uniform(118, 158),
            "set_pressure": rng.uniform(0.65, 1.05),
            "set_flow_rate": rng.uniform(34, 62),
            "line_speed": rng.uniform(52, 96),
        }
        quality, energy, defect = simulate(row, rng)
        rows.append(
            [
                f"{row['material_moisture']:.4f}",
                int(row["material_grade"]),
                f"{row['ambient_temp']:.3f}",
                f"{row['target_quality']:.3f}",
                f"{row['set_temperature']:.3f}",
                f"{row['set_pressure']:.4f}",
                f"{row['set_flow_rate']:.3f}",
                f"{row['line_speed']:.3f}",
                f"{quality:.3f}",
                f"{energy:.3f}",
                f"{defect:.5f}",
            ]
        )

    with output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)
        writer.writerows(rows)

    print(f"saved {len(rows)} rows to {output}")


if __name__ == "__main__":
    main()
