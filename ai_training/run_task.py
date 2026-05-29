import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parent
PYTHON = Path(sys.executable)


TASKS = {
    "detection.make_data": {
        "script": ROOT / "detection" / "scripts" / "make_synthetic_detection_dataset.py",
        "args": ["--output", "--size", "--train-count", "--val-count", "--seed"],
        "defaults": {"--size": "320", "--train-count": "80", "--val-count": "20", "--seed": "42"},
    },
    "detection.train": {
        "script": ROOT / "detection" / "train_yolo.py",
        "args": ["--data", "--output", "--model", "--epochs", "--imgsz", "--batch", "--device"],
        "defaults": {"--model": "yolov8n.pt", "--epochs": "10", "--imgsz": "320", "--batch": "4", "--device": "cpu"},
    },
    "detection.predict": {
        "script": ROOT / "detection" / "predict_yolo.py",
        "args": ["--model", "--source", "--output", "--imgsz", "--conf", "--device"],
        "defaults": {"--imgsz": "320", "--conf": "0.25", "--device": "cpu"},
    },
    "detection.visualize": {
        "script": ROOT / "detection" / "visualize_predictions.py",
        "args": ["--predictions", "--output-dir", "--min-conf"],
        "defaults": {"--min-conf": "0.25"},
    },
    "equipment.make_data": {
        "script": ROOT / "equipment" / "scripts" / "make_synthetic_equipment_data.py",
        "args": ["--output", "--equipment-count", "--hours", "--seed"],
        "defaults": {"--equipment-count": "6", "--hours": "480", "--seed": "42"},
    },
    "equipment.train_anomaly": {
        "script": ROOT / "equipment" / "train_anomaly_detector.py",
        "args": ["--data", "--output", "--threshold-percentile"],
        "defaults": {"--threshold-percentile": "99.0"},
    },
    "equipment.predict_anomaly": {
        "script": ROOT / "equipment" / "predict_anomaly.py",
        "args": ["--model-dir", "--data", "--output"],
        "defaults": {},
    },
    "equipment.train_fault": {
        "script": ROOT / "equipment" / "train_fault_predictor.py",
        "args": ["--data", "--output", "--epochs", "--lr", "--threshold"],
        "defaults": {"--epochs": "300", "--lr": "0.08", "--threshold": "0.5"},
    },
    "equipment.predict_fault": {
        "script": ROOT / "equipment" / "predict_fault.py",
        "args": ["--model-dir", "--data", "--output"],
        "defaults": {},
    },
    "equipment.plot_risk": {
        "script": ROOT / "equipment" / "plot_risk_trend.py",
        "args": ["--predictions", "--equipment-id", "--output", "--max-points"],
        "defaults": {"--max-points": "240"},
    },
    "process.make_data": {
        "script": ROOT / "process_optimization" / "scripts" / "make_synthetic_process_data.py",
        "args": ["--output", "--rows", "--seed"],
        "defaults": {"--rows": "3000", "--seed": "42"},
    },
    "process.train": {
        "script": ROOT / "process_optimization" / "train_process_models.py",
        "args": ["--data", "--output"],
        "defaults": {},
    },
    "process.optimize": {
        "script": ROOT / "process_optimization" / "optimize_parameters.py",
        "args": [
            "--model-dir",
            "--material-moisture",
            "--material-grade",
            "--ambient-temp",
            "--target-quality",
            "--output",
            "--candidates",
            "--seed",
            "--quality-weight",
            "--energy-weight",
            "--defect-weight",
        ],
        "defaults": {
            "--candidates": "8000",
            "--seed": "42",
            "--quality-weight": "8.0",
            "--energy-weight": "0.08",
            "--defect-weight": "180.0",
        },
    },
    "process.plot_candidates": {
        "script": ROOT / "process_optimization" / "plot_candidate_comparison.py",
        "args": ["--recommendation", "--output", "--top-n"],
        "defaults": {"--top-n": "6"},
    },
}


def parse_task_args(raw_args):
    parsed = {}
    i = 0
    while i < len(raw_args):
        key = raw_args[i]
        if not key.startswith("--"):
            raise SystemExit(f"Unexpected argument: {key}")
        if i + 1 >= len(raw_args) or raw_args[i + 1].startswith("--"):
            raise SystemExit(f"Missing value for {key}")
        parsed[key] = raw_args[i + 1]
        i += 2
    return parsed


def normalize_param_key(key):
    return "--" + key.replace("_", "-").lstrip("-")


def load_task_file(path):
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if "task" not in payload:
        raise SystemExit("Task file must include 'task'.")

    params = payload.get("params", {})
    if not isinstance(params, dict):
        raise SystemExit("Task file 'params' must be an object.")

    task_args = {normalize_param_key(key): str(value) for key, value in params.items()}
    return {
        "task": payload["task"],
        "task_id": payload.get("task_id"),
        "task_args": task_args,
        "task_result": payload.get("task_result"),
        "task_dir": payload.get("task_dir"),
    }


def build_command(task_name, task_args):
    spec = TASKS[task_name]
    values = dict(spec["defaults"])
    values.update(task_args)

    script = spec["script"].relative_to(ROOT.parent)
    command = [str(PYTHON), str(script)]
    for key in spec["args"]:
        if key in values:
            command.extend([key, values[key]])
    return command, values


def infer_result_path(task_name, values):
    if "--output" in values:
        return values["--output"]
    if "--output-dir" in values:
        return values["--output-dir"]
    return None


def make_task_id(task_name):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = uuid4().hex[:8]
    safe_name = task_name.replace(".", "_")
    return f"{timestamp}_{safe_name}_{suffix}"


def default_task_dir(task_id):
    return ROOT / "task_runs" / task_id


def write_task_result(path, payload):
    result_path = Path(path)
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def display_path(path):
    path = Path(path)
    try:
        return str(path.relative_to(ROOT.parent))
    except ValueError:
        return str(path)


def tail_text(text, limit=1200):
    if not text:
        return None
    return text[-limit:]


def main():
    parser = argparse.ArgumentParser(description="Unified entrypoint for AI training tasks.")
    parser.add_argument("--task", choices=sorted(TASKS))
    parser.add_argument("--task-file", help="JSON task file with task, task_id, and params.")
    parser.add_argument("--task-id", help="Optional platform task id.")
    parser.add_argument("--task-dir", help="Directory for logs and task_result.json.")
    parser.add_argument("--task-result", help="Optional path for unified task result JSON.")
    args, unknown = parser.parse_known_args()

    file_config = load_task_file(args.task_file) if args.task_file else {}
    task_name = args.task or file_config.get("task")
    if not task_name:
        raise SystemExit("Provide --task or --task-file.")
    if task_name not in TASKS:
        raise SystemExit(f"Unknown task: {task_name}")

    task_args = file_config.get("task_args", {})
    task_args.update(parse_task_args(unknown))
    task_id = args.task_id or file_config.get("task_id") or make_task_id(task_name)
    task_dir = Path(args.task_dir or file_config.get("task_dir") or default_task_dir(task_id))
    task_dir.mkdir(parents=True, exist_ok=True)

    command, values = build_command(task_name, task_args)
    started_at = datetime.now().isoformat(timespec="seconds")
    stdout_log = task_dir / "stdout.log"
    stderr_log = task_dir / "stderr.log"

    start_payload = {
        "task_id": task_id,
        "task": task_name,
        "command": command,
        "started_at": started_at,
        "task_dir": display_path(task_dir),
    }
    print(json.dumps(start_payload, ensure_ascii=False, indent=2))
    completed = subprocess.run(command, cwd=str(ROOT.parent), text=True, capture_output=True)
    finished_at = datetime.now().isoformat(timespec="seconds")
    stdout_log.write_text(completed.stdout or "", encoding="utf-8")
    stderr_log.write_text(completed.stderr or "", encoding="utf-8")
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)

    result = {
        "task_id": task_id,
        "task": task_name,
        "status": "success" if completed.returncode == 0 else "failed",
        "return_code": completed.returncode,
        "started_at": started_at,
        "finished_at": finished_at,
        "script": str(TASKS[task_name]["script"].relative_to(ROOT.parent)),
        "result_path": infer_result_path(task_name, values),
        "task_dir": display_path(task_dir),
        "stdout_log": display_path(stdout_log),
        "stderr_log": display_path(stderr_log),
        "error": tail_text(completed.stderr) if completed.returncode else None,
    }

    result_path = args.task_result or file_config.get("task_result")
    if not result_path and result["result_path"]:
        output_path = Path(result["result_path"])
        if output_path.suffix:
            result_path = str(output_path.with_name("task_result.json"))
        else:
            result_path = str(output_path / "task_result.json")
    if not result_path:
        result_path = str(task_dir / "task_result.json")
    if result_path:
        write_task_result(result_path, result)
        result["task_result"] = result_path

    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
