# YOLO Detection Training

This folder contains the object detection training template.

Detection is useful for:

- defect boxes, such as scratch, stain, broken area
- people, vehicle, equipment detection
- industrial package or part localization

## Dataset Format

Use the standard YOLO layout:

```text
datasets/my_detection/
  dataset.yaml
  images/
    train/
      0001.jpg
    val/
      0002.jpg
  labels/
    train/
      0001.txt
    val/
      0002.txt
```

Each label line is:

```text
class_id x_center y_center width height
```

All coordinates are normalized to 0-1.

## Create Synthetic Defect Dataset

```powershell
& "C:\Users\86180\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" ai_training\detection\scripts\make_synthetic_detection_dataset.py --output ai_training\datasets\synthetic_detection
```

The synthetic dataset includes four defect classes:

```text
0 scratch
1 stain
2 crack
3 chip
```

## Install Dependencies

```powershell
& "C:\Users\86180\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m pip install ultralytics
```

## Train

Use `M:` to avoid Python path issues with Chinese folders:

```powershell
subst M: "C:\Users\86180\Documents\模型"
& "C:\Users\86180\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" ai_training\detection\train_yolo.py --data ai_training\datasets\synthetic_detection\dataset.yaml --output ai_training\outputs\yolo_sample --epochs 3
```

The script copies `best.pt`, `last.pt`, and `training_summary.json` to the output folder.

## Predict

```powershell
subst M: "C:\Users\86180\Documents\模型"
& "C:\Users\86180\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" M:\ai_training\detection\predict_yolo.py --model M:\ai_training\outputs\yolo_sample\best.pt --source M:\ai_training\datasets\synthetic_detection\images\val\00000.jpg --output M:\ai_training\outputs\yolo_sample\prediction.json
```

Prediction output:

```json
[
  {
    "image": "image path",
    "detections": [
      {
        "class_id": 0,
        "label": "scratch",
        "confidence": 0.75,
        "box_xyxy": [10.0, 20.0, 80.0, 50.0]
      }
    ]
  }
]
```

## Visualize Predictions

```powershell
& "C:\Users\86180\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" M:\ai_training\detection\visualize_predictions.py --predictions M:\ai_training\outputs\yolo_sample\prediction.json --output-dir M:\ai_training\outputs\yolo_sample\visualized --min-conf 0.25
```

For very short test training runs, use a lower confidence threshold only to verify drawing:

```powershell
& "C:\Users\86180\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" M:\ai_training\detection\visualize_predictions.py --predictions M:\ai_training\outputs\yolo_sample\prediction.json --output-dir M:\ai_training\outputs\yolo_sample\visualized --min-conf 0.001
```
