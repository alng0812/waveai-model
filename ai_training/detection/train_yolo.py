import argparse
import json
import shutil
import sys
from pathlib import Path


def build_runtime_dataset_yaml(data_path, output):
    text = data_path.read_text(encoding="utf-8")
    lines = []
    replaced = False
    for line in text.splitlines():
        if line.strip() == "path: .":
            lines.append(f"path: {data_path.parent.as_posix()}")
            replaced = True
        else:
            lines.append(line)

    if not replaced:
        return data_path

    runtime_yaml = output / "_runtime_dataset.yaml"
    runtime_yaml.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return runtime_yaml


def main():
    parser = argparse.ArgumentParser(description="Train a YOLO detector with Ultralytics.")
    parser.add_argument("--data", required=True, help="Path to YOLO dataset.yaml.")
    parser.add_argument("--output", required=True, help="Output directory for training artifacts.")
    parser.add_argument("--model", default="yolov8n.pt", help="Base model, such as yolov8n.pt.")
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--device", default="cpu", help="Use cpu, 0, 1, etc.")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    for local_deps in reversed([project_root / ".deps_yolo", project_root / ".deps"]):
        if local_deps.exists():
            sys.path.insert(0, str(local_deps))

    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise SystemExit(
            "Missing dependency: ultralytics. Install it with: "
            "python -m pip install ultralytics"
        ) from exc

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    data_path = build_runtime_dataset_yaml(Path(args.data), output)

    model = YOLO(args.model)
    result = model.train(
        data=str(data_path),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        project=str(output),
        name="run",
        exist_ok=True,
    )

    save_dir = Path(result.save_dir)
    weights_dir = save_dir / "weights"
    best = weights_dir / "best.pt"
    last = weights_dir / "last.pt"

    if best.exists():
        shutil.copy2(best, output / "best.pt")
    if last.exists():
        shutil.copy2(last, output / "last.pt")

    summary = {
        "data": str(Path(args.data)),
        "model": args.model,
        "epochs": args.epochs,
        "imgsz": args.imgsz,
        "batch": args.batch,
        "device": args.device,
        "ultralytics_run_dir": str(save_dir),
        "best_model": str(output / "best.pt") if best.exists() else None,
        "last_model": str(output / "last.pt") if last.exists() else None,
    }

    (output / "training_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
