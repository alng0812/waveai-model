# Process Parameter Optimization

This module is for industrial process parameter optimization.

It answers a practical question:

```text
Given material and environment conditions, what temperature, pressure, flow rate, and line speed should we use?
```

The first version trains two regression models:

- quality model: predicts final product quality score
- energy model: predicts energy consumption

Then it searches parameter combinations and recommends the best settings.

## Data Columns

```text
material_moisture,material_grade,ambient_temp,target_quality,
set_temperature,set_pressure,set_flow_rate,line_speed,
quality_score,energy_consumption,defect_rate
```

Inputs:

- `material_moisture`: raw material moisture
- `material_grade`: material grade, 1-3
- `ambient_temp`: environment temperature
- `target_quality`: desired quality score

Controllable parameters:

- `set_temperature`
- `set_pressure`
- `set_flow_rate`
- `line_speed`

Outputs:

- `quality_score`
- `energy_consumption`
- `defect_rate`

## Generate Synthetic Data

```powershell
& "C:\Users\86180\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" ai_training\process_optimization\scripts\make_synthetic_process_data.py --output ai_training\process_optimization\data\process_data.csv
```

## Train Models

```powershell
& "C:\Users\86180\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" ai_training\process_optimization\train_process_models.py --data ai_training\process_optimization\data\process_data.csv --output ai_training\process_optimization\outputs\process_models
```

## Optimize Parameters

```powershell
& "C:\Users\86180\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" ai_training\process_optimization\optimize_parameters.py --model-dir ai_training\process_optimization\outputs\process_models --material-moisture 0.18 --material-grade 2 --ambient-temp 26 --target-quality 92 --output ai_training\process_optimization\outputs\recommendation.json
```

## Plot Candidate Comparison

```powershell
& "C:\Users\86180\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" ai_training\process_optimization\plot_candidate_comparison.py --recommendation ai_training\process_optimization\outputs\recommendation.json --output ai_training\process_optimization\outputs\candidate_comparison.jpg
```

## Output Meaning

The recommendation contains:

- recommended setpoints
- predicted quality score
- predicted energy consumption
- predicted defect rate
- top candidate parameter sets

In a real factory, this kind of model can help operators choose stable process parameters before production starts.
