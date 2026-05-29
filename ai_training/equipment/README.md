# Equipment Anomaly and Fault Prediction

This module is for industrial equipment sensor data.

It covers two common tasks:

1. Anomaly detection: find rows that look abnormal compared with normal operation.
2. Fault prediction: estimate whether a fault may happen soon.

## Example Data

Each row represents one sensor snapshot:

```text
timestamp,equipment_id,temperature,vibration,current,pressure,rpm,load,anomaly,fault_within_24h
2026-01-01 00:00:00,pump_01,61.2,0.18,12.1,0.82,1480,0.64,0,0
```

Fields:

- `temperature`: equipment temperature
- `vibration`: vibration strength
- `current`: motor current
- `pressure`: pressure value
- `rpm`: rotation speed
- `load`: production load
- `anomaly`: 1 means abnormal, 0 means normal
- `fault_within_24h`: 1 means a fault is likely within the next 24 hours

## Generate Synthetic Data

```powershell
& "C:\Users\86180\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" ai_training\equipment\scripts\make_synthetic_equipment_data.py --output ai_training\equipment\data\equipment_sensor_data.csv
```

## Train Anomaly Detector

```powershell
& "C:\Users\86180\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" ai_training\equipment\train_anomaly_detector.py --data ai_training\equipment\data\equipment_sensor_data.csv --output ai_training\equipment\outputs\anomaly_model
```

## Predict Anomalies

```powershell
& "C:\Users\86180\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" ai_training\equipment\predict_anomaly.py --model-dir ai_training\equipment\outputs\anomaly_model --data ai_training\equipment\data\equipment_sensor_data.csv --output ai_training\equipment\outputs\anomaly_predictions.csv
```

## Train Fault Predictor

```powershell
& "C:\Users\86180\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" ai_training\equipment\train_fault_predictor.py --data ai_training\equipment\data\equipment_sensor_data.csv --output ai_training\equipment\outputs\fault_model --epochs 300
```

## Predict Fault Risk

```powershell
& "C:\Users\86180\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" ai_training\equipment\predict_fault.py --model-dir ai_training\equipment\outputs\fault_model --data ai_training\equipment\data\equipment_sensor_data.csv --output ai_training\equipment\outputs\fault_predictions.csv
```

## Plot Fault Risk Trend

```powershell
& "C:\Users\86180\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" ai_training\equipment\plot_risk_trend.py --predictions ai_training\equipment\outputs\fault_predictions.csv --equipment-id pump_01 --output ai_training\equipment\outputs\pump_01_risk_trend.jpg
```

## How To Read Results

Anomaly output:

```text
anomaly_score,predicted_anomaly
```

Fault output:

```text
fault_risk,predicted_fault
```

In a real factory, this can be used for:

- warning when sensors drift away from normal range
- finding equipment that needs inspection
- estimating fault risk before production stops
- supporting maintenance planning
