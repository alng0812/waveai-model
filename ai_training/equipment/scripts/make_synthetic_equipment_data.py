import argparse
import csv
import math
import random
from datetime import datetime, timedelta
from pathlib import Path


HEADER = [
    "timestamp",
    "equipment_id",
    "temperature",
    "vibration",
    "current",
    "pressure",
    "rpm",
    "load",
    "anomaly",
    "fault_within_24h",
]


def clamp(value, low, high):
    return max(low, min(high, value))


def generate_equipment_rows(equipment_id, start_time, hours, rng):
    rows = []
    base_temp = rng.uniform(55, 65)
    base_vibration = rng.uniform(0.12, 0.22)
    base_current = rng.uniform(10.5, 13.5)
    base_pressure = rng.uniform(0.72, 0.9)
    base_rpm = rng.uniform(1420, 1510)

    fault_window = max(12, min(72, hours // 5))
    latest_start = max(hours // 2, hours - fault_window - 1)
    fault_start = rng.randint(max(1, hours // 3), latest_start)
    fault_end = min(hours - 1, fault_start + fault_window)

    for hour in range(hours):
        timestamp = start_time + timedelta(hours=hour)
        day_cycle = math.sin(hour / 24 * math.pi * 2)
        load = clamp(0.62 + 0.16 * day_cycle + rng.gauss(0, 0.05), 0.25, 0.98)

        degradation = 0.0
        if fault_start <= hour <= fault_end:
            degradation = (hour - fault_start) / max(1, fault_end - fault_start)

        random_spike = rng.random() < 0.025
        spike = rng.uniform(0.7, 1.5) if random_spike else 0.0

        temperature = base_temp + load * 9 + degradation * 24 + spike * 8 + rng.gauss(0, 1.5)
        vibration = base_vibration + load * 0.09 + degradation * 0.55 + spike * 0.18 + rng.gauss(0, 0.025)
        current = base_current + load * 2.2 + degradation * 4.5 + spike * 1.3 + rng.gauss(0, 0.35)
        pressure = base_pressure + load * 0.08 - degradation * 0.18 - spike * 0.05 + rng.gauss(0, 0.025)
        rpm = base_rpm - degradation * 115 - spike * 35 + rng.gauss(0, 18)

        anomaly = int(
            random_spike
            or temperature > 82
            or vibration > 0.52
            or current > 18
            or pressure < 0.62
            or rpm < 1340
        )
        fault_within_24h = int(fault_start <= hour <= fault_end and degradation > 0.55)

        rows.append(
            [
                timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                equipment_id,
                f"{temperature:.3f}",
                f"{vibration:.4f}",
                f"{current:.3f}",
                f"{pressure:.4f}",
                f"{rpm:.2f}",
                f"{load:.4f}",
                anomaly,
                fault_within_24h,
            ]
        )
    return rows


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic equipment sensor data.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--equipment-count", type=int, default=6)
    parser.add_argument("--hours", type=int, default=480)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    start_time = datetime(2026, 1, 1, 0, 0, 0)

    rows = []
    for i in range(args.equipment_count):
        equipment_id = f"pump_{i + 1:02d}"
        rows.extend(generate_equipment_rows(equipment_id, start_time, args.hours, rng))

    with output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)
        writer.writerows(rows)

    print(f"saved {len(rows)} rows to {output}")


if __name__ == "__main__":
    main()
