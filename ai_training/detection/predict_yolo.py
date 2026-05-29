import argparse
import json
import sys
from pathlib import Path


def load_local_deps():
    project_root = Path(__file__).resolve().parents[1]
    for local_deps in reversed([project_root / ".deps_yolo", project_root / ".deps"]):
        if local_deps.exists():
            sys.path.insert(0, str(local_deps))


def main():
    parser = argparse.ArgumentParser(description="Predict objects with a YOLO model.")
    parser.add_argument("--model", required=True, help="Path to best.pt or last.pt.")
    parser.add_argument("--source", required=True, help="Image path or folder.")
    parser.add_argument("--output", help="Optional JSON output path.")
    parser.add_argument("--imgsz", type=int, default=320)
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()

    load_local_deps()
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise SystemExit("Missing dependency: ultralytics. Install ai_training/.deps_yolo first.") from exc

    model = YOLO(args.model)
    results = model.predict(args.source, imgsz=args.imgsz, conf=args.conf, device=args.device, verbose=False)

    payload = []
    for result in results:
        image_result = {
            "image": str(result.path),
            "detections": [],
        }
        names = result.names
        for box in result.boxes:
            class_id = int(box.cls[0])
            xyxy = [float(v) for v in box.xyxy[0].tolist()]
            image_result["detections"].append(
                {
                    "class_id": class_id,
                    "label": names.get(class_id, str(class_id)),
                    "confidence": float(box.conf[0]),
                    "box_xyxy": xyxy,
                }
            )
        payload.append(image_result)

    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
