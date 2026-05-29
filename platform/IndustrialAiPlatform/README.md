# Industrial Model Training Platform Demo

This is a small ASP.NET Core demo platform for the algorithm layer in `ai_training`.

It provides:

- frontend task configuration page
- backend API for task submission
- Python execution through `ai_training/run_task.py`
- task status polling
- stdout/stderr log reading
- recent task history
- output preview for JSON, CSV, and images
- CSV upload for training and prediction input files

## Run

From the workspace root:

```powershell
dotnet run --project platform\IndustrialAiPlatform\IndustrialAiPlatform.csproj --urls http://localhost:5088
```

Then open:

```text
http://localhost:5088
```

## API

List modules:

```text
GET /api/modules
```

Submit a task:

```text
POST /api/tasks
```

Upload a CSV file:

```text
POST /api/uploads/csv
Content-Type: multipart/form-data
```

The response contains the stored relative path. Use that path in task fields such as `data` or `predictions`.
For known CSV task fields, the response also includes validation details:

- required columns
- missing columns
- suggested mappings, for example `温度 -> temperature`
- whether the file is usable for the selected task

Apply CSV header mappings:

```text
POST /api/uploads/csv/map
Content-Type: application/json
```

Example body:

```json
{
  "path": "platform_data\\uploads\\example.csv",
  "task": "equipment.train_fault",
  "fieldName": "data",
  "mappings": {
    "temperature": "温度",
    "vibration": "震动",
    "fault_within_24h": "故障"
  }
}
```

Example body:

```json
{
  "task": "process.optimize",
  "params": {
    "model_dir": "ai_training/process_optimization/outputs/process_models",
    "material_moisture": 0.18,
    "material_grade": 2,
    "ambient_temp": 26,
    "target_quality": 92,
    "output": "ai_training/process_optimization/outputs/platform_recommendation.json",
    "candidates": 1200
  }
}
```

Check task:

```text
GET /api/tasks/{taskId}
```

Read logs:

```text
GET /api/tasks/{taskId}/logs
```

List recent tasks:

```text
GET /api/tasks
```

Preview task output:

```text
GET /api/tasks/{taskId}/output
```

## Notes

The backend uses the bundled Codex Python by default:

```text
C:\Users\86180\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe
```

Override it with:

```powershell
$env:AI_PLATFORM_PYTHON="C:\path\to\python.exe"
```

Runtime task files are written to:

```text
platform_data/tasks/
```
