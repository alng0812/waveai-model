# Unified Task Entrypoint

Use `run_task.py` when a platform wants one stable command surface for all algorithm modules.

General form:

```powershell
& "C:\Users\86180\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" ai_training\run_task.py --task TASK_NAME [task args]
```

JSON task form:

```powershell
& "C:\Users\86180\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" ai_training\run_task.py --task-file ai_training\examples\process_optimize_task.json
```

After the child task finishes, `run_task.py` writes:

```text
task_result.json
stdout.log
stderr.log
```

## Task Names

```text
detection.make_data
detection.train
detection.predict
detection.visualize
equipment.make_data
equipment.train_anomaly
equipment.predict_anomaly
equipment.train_fault
equipment.predict_fault
equipment.plot_risk
process.make_data
process.train
process.optimize
process.plot_candidates
```

## Examples

Generate equipment data:

```powershell
& "C:\Users\86180\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" ai_training\run_task.py --task equipment.make_data --output ai_training\equipment\data\equipment_sensor_data.csv
```

Train fault model:

```powershell
& "C:\Users\86180\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" ai_training\run_task.py --task equipment.train_fault --data ai_training\equipment\data\equipment_sensor_data.csv --output ai_training\equipment\outputs\fault_model --epochs 300
```

Optimize process parameters:

```powershell
& "C:\Users\86180\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" ai_training\run_task.py --task process.optimize --model-dir ai_training\process_optimization\outputs\process_models --material-moisture 0.18 --material-grade 2 --ambient-temp 26 --target-quality 92 --output ai_training\process_optimization\outputs\recommendation.json
```

## Result JSON

Example:

```json
{
  "task_id": "demo_process_optimize_001",
  "task": "process.optimize",
  "status": "success",
  "return_code": 0,
  "started_at": "2026-05-29T15:30:00",
  "finished_at": "2026-05-29T15:30:02",
  "script": "script path",
  "result_path": "main output path",
  "task_dir": "log directory",
  "stdout_log": "stdout.log path",
  "stderr_log": "stderr.log path",
  "error": null
}
```

The C# platform can read this file to update task status.

## JSON Task File

Example:

```json
{
  "task_id": "demo_process_optimize_001",
  "task": "process.optimize",
  "params": {
    "model_dir": "ai_training/process_optimization/outputs/process_models",
    "material_moisture": 0.18,
    "material_grade": 2,
    "ambient_temp": 26,
    "target_quality": 92,
    "output": "ai_training/process_optimization/outputs/json_task_recommendation.json",
    "candidates": 1000
  }
}
```

Parameter names in JSON use underscores, and `run_task.py` converts them to command-line flags. For example:

```text
model_dir -> --model-dir
target_quality -> --target-quality
```
