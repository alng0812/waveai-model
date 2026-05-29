# 算法模块说明书

这份文档整理当前 `ai_training` 目录下的工业 AI 原型模块。它面向两个用途：

1. 你自己理解每个算法模块能做什么
2. 以后 C# 平台调用这些算法时有统一参考

当前项目不是完整训练平台，而是平台里的“算法层”。可以理解成：

```text
C# 平台负责界面、用户、任务、文件管理
Python 算法层负责训练、预测、优化、输出结果
```

## 总览

| 模块 | 目录 | 输入 | 输出 | 典型用途 |
| --- | --- | --- | --- | --- |
| 图片缺陷检测 | `detection/` | 图片和 YOLO 标注 | `best.pt`、预测 JSON、标注图 | 外观缺陷、包装破损、零件检测 |
| 设备异常/故障预测 | `equipment/` | 传感器 CSV | 异常分数、故障风险、趋势图 | 预测性维护、停机预警 |
| 工艺参数优化 | `process_optimization/` | 工艺历史 CSV、当前工况 | 推荐参数、候选对比图 | 质量稳定、节能、降低缺陷率 |

## 统一调用方式

每个模块都遵循相似流程：

```text
生成或准备数据 -> 训练模型 -> 预测/优化 -> 输出结果文件
```

C# 平台以后可以通过启动 Python 进程调用，例如：

```text
python script.py --data input.csv --output output_dir
```

平台只需要关心：

- 输入文件路径
- 参数
- 输出文件路径
- 训练日志和退出码

## 1. 图片缺陷检测

目录：

```text
ai_training/detection
```

作用：

用 YOLO 模型检测图片里的缺陷位置，并输出检测框。

当前模拟缺陷类别：

```text
scratch  划痕
stain    污点
crack    裂纹
chip     缺口
```

### 数据格式

使用 YOLO 标准格式：

```text
dataset/
  dataset.yaml
  images/
    train/
    val/
  labels/
    train/
    val/
```

每个标签文件内容类似：

```text
0 0.512 0.431 0.120 0.085
```

含义：

```text
class_id x_center y_center width height
```

坐标是 0-1 的相对比例。

### 生成模拟数据

```powershell
& "C:\Users\86180\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" ai_training\detection\scripts\make_synthetic_detection_dataset.py --output ai_training\datasets\synthetic_detection
```

### 训练

建议先映射英文盘符：

```powershell
subst M: "C:\Users\86180\Documents\模型"
```

训练命令：

```powershell
& "C:\Users\86180\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" M:\ai_training\detection\train_yolo.py --data M:\ai_training\datasets\synthetic_detection\dataset.yaml --output M:\ai_training\outputs\yolo_defect_sample --epochs 30 --imgsz 320 --batch 4 --device cpu
```

主要输出：

```text
best.pt   最佳模型
last.pt   最后一轮模型
training_summary.json
```

### 预测

```powershell
& "C:\Users\86180\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" M:\ai_training\detection\predict_yolo.py --model M:\ai_training\outputs\yolo_defect_sample\best.pt --source M:\ai_training\datasets\synthetic_detection\images\val\00000.jpg --output M:\ai_training\outputs\yolo_defect_sample\prediction.json --conf 0.25 --imgsz 320 --device cpu
```

预测 JSON 示例：

```json
[
  {
    "image": "image path",
    "detections": [
      {
        "class_id": 2,
        "label": "crack",
        "confidence": 0.82,
        "box_xyxy": [29.2, 201.6, 135.1, 216.7]
      }
    ]
  }
]
```

### 可视化

```powershell
& "C:\Users\86180\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" M:\ai_training\detection\visualize_predictions.py --predictions M:\ai_training\outputs\yolo_defect_sample\prediction.json --output-dir M:\ai_training\outputs\yolo_defect_sample\visualized --min-conf 0.25
```

输出：

```text
visualized/xxx_annotated.jpg
```

## 2. 设备异常/故障预测

目录：

```text
ai_training/equipment
```

作用：

用设备传感器数据判断当前是否异常，并预测未来是否可能故障。

### 数据字段

```text
timestamp
equipment_id
temperature
vibration
current
pressure
rpm
load
anomaly
fault_within_24h
```

其中：

- `anomaly`: 当前是否异常，1 表示异常
- `fault_within_24h`: 未来 24 小时是否可能故障，1 表示有风险

### 生成模拟数据

```powershell
& "C:\Users\86180\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" ai_training\equipment\scripts\make_synthetic_equipment_data.py --output ai_training\equipment\data\equipment_sensor_data.csv
```

### 训练异常检测模型

```powershell
& "C:\Users\86180\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" ai_training\equipment\train_anomaly_detector.py --data ai_training\equipment\data\equipment_sensor_data.csv --output ai_training\equipment\outputs\anomaly_model
```

输出：

```text
anomaly_model/model.json
anomaly_model/metrics.json
```

### 预测异常

```powershell
& "C:\Users\86180\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" ai_training\equipment\predict_anomaly.py --model-dir ai_training\equipment\outputs\anomaly_model --data ai_training\equipment\data\equipment_sensor_data.csv --output ai_training\equipment\outputs\anomaly_predictions.csv
```

输出字段：

```text
anomaly_score
predicted_anomaly
```

### 训练故障预测模型

```powershell
& "C:\Users\86180\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" ai_training\equipment\train_fault_predictor.py --data ai_training\equipment\data\equipment_sensor_data.csv --output ai_training\equipment\outputs\fault_model --epochs 300
```

### 预测故障风险

```powershell
& "C:\Users\86180\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" ai_training\equipment\predict_fault.py --model-dir ai_training\equipment\outputs\fault_model --data ai_training\equipment\data\equipment_sensor_data.csv --output ai_training\equipment\outputs\fault_predictions.csv
```

输出字段：

```text
fault_risk
predicted_fault
```

### 风险趋势图

```powershell
& "C:\Users\86180\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" ai_training\equipment\plot_risk_trend.py --predictions ai_training\equipment\outputs\fault_predictions.csv --equipment-id pump_01 --output ai_training\equipment\outputs\pump_01_risk_trend.jpg
```

输出：

```text
pump_01_risk_trend.jpg
```

## 3. 工艺参数优化

目录：

```text
ai_training/process_optimization
```

作用：

根据原料、环境和目标质量，推荐工艺参数。

可以理解成：

```text
输入当前工况 -> 预测不同参数下的质量/能耗/缺陷率 -> 选出综合最优参数
```

### 数据字段

上下文条件：

```text
material_moisture
material_grade
ambient_temp
target_quality
```

可控制参数：

```text
set_temperature
set_pressure
set_flow_rate
line_speed
```

预测目标：

```text
quality_score
energy_consumption
defect_rate
```

### 生成模拟数据

```powershell
& "C:\Users\86180\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" ai_training\process_optimization\scripts\make_synthetic_process_data.py --output ai_training\process_optimization\data\process_data.csv
```

### 训练模型

```powershell
& "C:\Users\86180\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" ai_training\process_optimization\train_process_models.py --data ai_training\process_optimization\data\process_data.csv --output ai_training\process_optimization\outputs\process_models
```

输出：

```text
process_models/model.json
process_models/metrics.json
```

### 推荐参数

```powershell
& "C:\Users\86180\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" ai_training\process_optimization\optimize_parameters.py --model-dir ai_training\process_optimization\outputs\process_models --material-moisture 0.18 --material-grade 2 --ambient-temp 26 --target-quality 92 --output ai_training\process_optimization\outputs\recommendation.json
```

输出 JSON 里包含：

```text
context          当前工况
recommendation   推荐参数
top_candidates   前 10 个候选方案
control_ranges   参数搜索范围
```

推荐结果示例：

```json
{
  "controls": {
    "set_temperature": 138.8022,
    "set_pressure": 0.8788,
    "set_flow_rate": 57.9905,
    "line_speed": 74.204
  },
  "prediction": {
    "quality_score": 92.31393,
    "energy_consumption": 130.86687,
    "defect_rate": 0.07815
  }
}
```

### 候选方案对比图

```powershell
& "C:\Users\86180\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" ai_training\process_optimization\plot_candidate_comparison.py --recommendation ai_training\process_optimization\outputs\recommendation.json --output ai_training\process_optimization\outputs\candidate_comparison.jpg
```

输出：

```text
candidate_comparison.jpg
```

## C# 平台如何接入

未来 C# 后台可以这样做：

1. 用户上传数据文件
2. 后台生成一个训练任务编号
3. 后台启动对应 Python 脚本
4. 后台持续读取日志或等待进程结束
5. 训练完成后读取输出目录
6. 页面展示指标、模型文件、预测结果或图片

概念示例：

```csharp
var psi = new ProcessStartInfo
{
    FileName = pythonExe,
    Arguments = "ai_training\\equipment\\train_fault_predictor.py --data input.csv --output outputs\\fault_model",
    WorkingDirectory = projectRoot,
    RedirectStandardOutput = true,
    RedirectStandardError = true,
    UseShellExecute = false
};
```

平台需要保存的任务信息：

```text
task_id
module_name
input_path
output_path
status
started_at
finished_at
metrics_path
result_path
```

## 当前限制

这些模块目前是原型，不是生产级系统：

- 数据都是模拟生成的
- 没有任务队列
- 没有权限管理
- 没有 Web 页面
- 没有 GPU 调度
- 没有模型版本库

但是算法调用方式、输入输出结构、训练预测流程已经搭好了，后续可以逐步接到 C# 平台里。

## 推荐下一步

已经新增统一任务入口：

```text
ai_training/run_task.py
```

让 C# 平台只调用一个脚本，通过任务名选择模块：

```text
--task detection.train
--task equipment.train_fault
--task process.optimize
```

统一入口详细说明见：

```text
ai_training/RUN_TASKS.md
```

平台更推荐使用 JSON 任务文件调用，例如：

```powershell
& "C:\Users\86180\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" ai_training\run_task.py --task-file ai_training\examples\process_optimize_task.json
```

当前已有一个 ASP.NET Core 平台 demo：

```text
platform/IndustrialAiPlatform
```

它提供前端配置界面和后端任务调用 API，可以作为后续 C# 平台的起点。
