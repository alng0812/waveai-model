# 工业算法训练原型

这个目录是训练平台的算法层原型。它暂时不包含 C# 平台页面和后台，只负责三件事：

1. 准备或读取数据
2. 训练模型
3. 输出预测、推荐结果和可视化图片

后续 C# 平台可以把这些脚本当作“算法发动机”调用。

## 当前模块

| 模块 | 目录 | 作用 |
| --- | --- | --- |
| 图片缺陷检测 | `detection/` | 用 YOLO 识别图片中的划痕、污点、裂纹、缺口等 |
| 设备异常/故障预测 | `equipment/` | 用传感器表格数据判断异常和故障风险 |
| 工艺参数优化 | `process_optimization/` | 根据原料和环境条件推荐温度、压力、流量、速度等参数 |

完整说明见：

```text
ai_training/ALGORITHM_MODULES.md
```

统一入口说明见：

```text
ai_training/RUN_TASKS.md
```

## Python

当前使用 Codex 自带 Python：

```powershell
& "C:\Users\86180\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" --version
```

YOLO 依赖安装在：

```text
ai_training/.deps_yolo
```

## 中文路径注意

YOLO/PyTorch 在 Windows 中文路径下可能出现路径编码问题。运行 YOLO 相关脚本时，建议先映射英文盘符：

```powershell
subst M: "C:\Users\86180\Documents\模型"
```

然后使用 `M:\ai_training\...` 路径运行脚本。

## 产物说明

训练和预测产生的数据、模型、图片一般放在各模块的 `outputs/` 目录中。它们已加入 `.gitignore`，避免误提交大文件。

## 推荐阅读顺序

1. 先读 `ALGORITHM_MODULES.md`
2. 再读每个子模块的 `README.md`
3. 最后看具体训练脚本
