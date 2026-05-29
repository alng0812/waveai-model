using System.Diagnostics;
using System.Text.Json;
using System.Text.Json.Serialization;

var initialWorkspaceRoot = FindWorkspaceRoot(Directory.GetCurrentDirectory());
var builder = WebApplication.CreateBuilder(new WebApplicationOptions
{
    Args = args,
    ContentRootPath = Path.Combine(initialWorkspaceRoot, "platform", "IndustrialAiPlatform"),
    WebRootPath = "wwwroot"
});
builder.Logging.ClearProviders();
builder.Logging.AddConsole();
var app = builder.Build();

var workspaceRoot = initialWorkspaceRoot;
var aiRoot = Path.Combine(workspaceRoot, "ai_training");
var platformData = Path.Combine(workspaceRoot, "platform_data", "tasks");
var pythonExe = Environment.GetEnvironmentVariable("AI_PLATFORM_PYTHON")
    ?? @"C:\Users\86180\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe";

Directory.CreateDirectory(platformData);

var jsonOptions = new JsonSerializerOptions
{
    PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
    WriteIndented = true,
    DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull
};

app.UseDefaultFiles();
app.UseStaticFiles();

app.MapGet("/api/modules", () => Results.Json(ModuleCatalog.All, jsonOptions));

app.MapPost("/api/tasks", async (TaskSubmitRequest request) =>
{
    if (string.IsNullOrWhiteSpace(request.Task))
    {
        return Results.BadRequest(new { error = "task is required" });
    }

    if (!ModuleCatalog.All.Any(module => module.Task == request.Task))
    {
        return Results.BadRequest(new { error = $"unknown task: {request.Task}" });
    }

    var taskId = string.IsNullOrWhiteSpace(request.TaskId)
        ? $"{DateTime.Now:yyyyMMdd_HHmmss}_{request.Task.Replace('.', '_')}_{Guid.NewGuid():N}"[..40]
        : request.TaskId;

    var taskDir = Path.Combine(platformData, taskId);
    Directory.CreateDirectory(taskDir);

    var taskFile = Path.Combine(taskDir, "task.json");
    var taskResult = Path.Combine(taskDir, "task_result.json");
    var payload = new
    {
        task_id = taskId,
        task = request.Task,
        task_dir = ToRelativePath(workspaceRoot, taskDir),
        task_result = ToRelativePath(workspaceRoot, taskResult),
        @params = NormalizeParams(request.Params)
    };

    await File.WriteAllTextAsync(taskFile, JsonSerializer.Serialize(payload, jsonOptions));

    var process = new Process
    {
        StartInfo = new ProcessStartInfo
        {
            FileName = pythonExe,
            Arguments = $"ai_training\\run_task.py --task-file \"{ToRelativePath(workspaceRoot, taskFile)}\"",
            WorkingDirectory = workspaceRoot,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true
        },
        EnableRaisingEvents = true
    };

    var hostStdout = Path.Combine(taskDir, "host_stdout.log");
    var hostStderr = Path.Combine(taskDir, "host_stderr.log");
    var stdoutLock = new object();
    var stderrLock = new object();
    process.OutputDataReceived += (_, e) =>
    {
        if (e.Data is null) return;
        lock (stdoutLock)
        {
            File.AppendAllText(hostStdout, e.Data + Environment.NewLine);
        }
    };
    process.ErrorDataReceived += (_, e) =>
    {
        if (e.Data is null) return;
        lock (stderrLock)
        {
            File.AppendAllText(hostStderr, e.Data + Environment.NewLine);
        }
    };

    process.Start();
    process.BeginOutputReadLine();
    process.BeginErrorReadLine();

    _ = Task.Run(async () =>
    {
        await process.WaitForExitAsync();
        process.Dispose();
    });

    var accepted = new
    {
        taskId,
        request.Task,
        status = "running",
        taskDir = ToRelativePath(workspaceRoot, taskDir),
        taskFile = ToRelativePath(workspaceRoot, taskFile),
        taskResult = ToRelativePath(workspaceRoot, taskResult)
    };

    return Results.Accepted($"/api/tasks/{taskId}", accepted);
});

app.MapGet("/api/tasks/{taskId}", async (string taskId) =>
{
    var taskDir = Path.Combine(platformData, taskId);
    if (!Directory.Exists(taskDir))
    {
        return Results.NotFound(new { error = "task not found" });
    }

    var resultPath = Path.Combine(taskDir, "task_result.json");
    if (!File.Exists(resultPath))
    {
        return Results.Json(new
        {
            taskId,
            status = "running",
            taskDir = ToRelativePath(workspaceRoot, taskDir),
            logs = new
            {
                hostStdout = ReadTail(Path.Combine(taskDir, "host_stdout.log")),
                hostStderr = ReadTail(Path.Combine(taskDir, "host_stderr.log"))
            }
        }, jsonOptions);
    }

    var result = await File.ReadAllTextAsync(resultPath);
    return Results.Text(result, "application/json");
});

app.MapGet("/api/tasks/{taskId}/logs", (string taskId) =>
{
    var taskDir = Path.Combine(platformData, taskId);
    if (!Directory.Exists(taskDir))
    {
        return Results.NotFound(new { error = "task not found" });
    }

    return Results.Json(new
    {
        hostStdout = ReadTail(Path.Combine(taskDir, "host_stdout.log")),
        hostStderr = ReadTail(Path.Combine(taskDir, "host_stderr.log")),
        stdout = ReadTail(Path.Combine(taskDir, "stdout.log")),
        stderr = ReadTail(Path.Combine(taskDir, "stderr.log"))
    }, jsonOptions);
});

app.MapGet("/api/tasks/{taskId}/output", async (string taskId) =>
{
    var taskDir = Path.Combine(platformData, taskId);
    if (!Directory.Exists(taskDir))
    {
        return Results.NotFound(new { error = "task not found" });
    }

    var resultPath = Path.Combine(taskDir, "task_result.json");
    if (!File.Exists(resultPath))
    {
        return Results.NotFound(new { error = "task result not found" });
    }

    var result = JsonSerializer.Deserialize<TaskResultFile>(await File.ReadAllTextAsync(resultPath), jsonOptions);
    if (string.IsNullOrWhiteSpace(result?.ResultPath))
    {
        return Results.NotFound(new
        {
            error = "result_path not found",
            message = "This task did not produce a standalone preview file. Check the result JSON and logs."
        });
    }

    var outputPath = ResolveWorkspacePath(workspaceRoot, result.ResultPath);
    if (!File.Exists(outputPath))
    {
        return Results.NotFound(new
        {
            error = "output file not found",
            path = result.ResultPath,
            message = "The task result points to a directory or a file that is not available for preview."
        });
    }

    var extension = Path.GetExtension(outputPath).ToLowerInvariant();
    if (extension is ".jpg" or ".jpeg" or ".png")
    {
        return Results.File(outputPath, extension == ".png" ? "image/png" : "image/jpeg");
    }

    var text = await File.ReadAllTextAsync(outputPath);
    return Results.Json(new
    {
        path = result.ResultPath,
        kind = extension.TrimStart('.'),
        content = text
    }, jsonOptions);
});

app.MapGet("/api/tasks", () =>
{
    var tasks = Directory.GetDirectories(platformData)
        .OrderByDescending(Directory.GetLastWriteTimeUtc)
        .Take(30)
        .Select(dir =>
        {
            var resultPath = Path.Combine(dir, "task_result.json");
            var taskFile = Path.Combine(dir, "task.json");
            var result = TryReadTaskResult(resultPath);
            return new
            {
                taskId = Path.GetFileName(dir),
                status = result?.Status ?? (File.Exists(resultPath) ? "finished" : "running"),
                task = TryReadTaskName(taskFile),
                resultPath = result?.ResultPath,
                updatedAt = Directory.GetLastWriteTime(dir).ToString("yyyy-MM-dd HH:mm:ss")
            };
        });

    return Results.Json(tasks, jsonOptions);
});

app.MapFallbackToFile("index.html");

app.Run();

static Dictionary<string, object?> NormalizeParams(Dictionary<string, JsonElement>? input)
{
    var result = new Dictionary<string, object?>();
    if (input is null) return result;

    foreach (var (key, value) in input)
    {
        result[key] = value.ValueKind switch
        {
            JsonValueKind.Number when value.TryGetInt64(out var longValue) => longValue,
            JsonValueKind.Number when value.TryGetDouble(out var doubleValue) => doubleValue,
            JsonValueKind.True => true,
            JsonValueKind.False => false,
            JsonValueKind.Null => null,
            _ => value.GetString()
        };
    }

    return result;
}

static string ToRelativePath(string root, string path) =>
    Path.GetRelativePath(root, path).Replace("/", "\\");

static string ReadTail(string path, int maxChars = 6000)
{
    if (!File.Exists(path)) return "";
    var text = File.ReadAllText(path);
    return text.Length <= maxChars ? text : text[^maxChars..];
}

static string? TryReadTaskName(string taskFile)
{
    if (!File.Exists(taskFile)) return null;
    try
    {
        using var doc = JsonDocument.Parse(File.ReadAllText(taskFile));
        return doc.RootElement.TryGetProperty("task", out var task) ? task.GetString() : null;
    }
    catch
    {
        return null;
    }
}

static TaskResultFile? TryReadTaskResult(string resultFile)
{
    if (!File.Exists(resultFile)) return null;
    try
    {
        return JsonSerializer.Deserialize<TaskResultFile>(File.ReadAllText(resultFile), new JsonSerializerOptions
        {
            PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
            PropertyNameCaseInsensitive = true
        });
    }
    catch
    {
        return null;
    }
}

static string ResolveWorkspacePath(string root, string relativePath)
{
    var normalized = relativePath.Replace('/', Path.DirectorySeparatorChar).Replace('\\', Path.DirectorySeparatorChar);
    var fullPath = Path.GetFullPath(Path.Combine(root, normalized));
    if (!fullPath.StartsWith(root, StringComparison.OrdinalIgnoreCase))
    {
        throw new InvalidOperationException("Path escapes workspace root.");
    }
    return fullPath;
}

static string FindWorkspaceRoot(string startPath)
{
    var candidates = new[]
    {
        startPath,
        AppContext.BaseDirectory,
        Directory.GetCurrentDirectory()
    };

    foreach (var candidate in candidates)
    {
        var directory = new DirectoryInfo(candidate);
        while (directory is not null)
        {
            if (Directory.Exists(Path.Combine(directory.FullName, "ai_training")))
            {
                return directory.FullName;
            }
            directory = directory.Parent;
        }
    }

    throw new DirectoryNotFoundException("Could not locate workspace root containing ai_training.");
}

record TaskSubmitRequest(string? TaskId, string Task, Dictionary<string, JsonElement>? Params);

record TaskResultFile(
    string TaskId,
    string Task,
    string Status,
    [property: JsonPropertyName("result_path")] string? ResultPath
);

record ModuleDefinition(string Task, string Title, string Domain, string Description, FieldDefinition[] Fields);

record FieldDefinition(string Name, string Label, string Type, string DefaultValue, string Hint = "");

static class ModuleCatalog
{
    public static readonly ModuleDefinition[] All =
    [
        new(
            "process.optimize",
            "工艺参数优化",
            "Process",
            "根据原料水分、等级、环境温度和目标质量推荐温度、压力、流量、线速。",
            [
                new("model_dir", "模型目录", "text", "ai_training/process_optimization/outputs/process_models"),
                new("material_moisture", "原料水分", "number", "0.18"),
                new("material_grade", "原料等级", "number", "2"),
                new("ambient_temp", "环境温度", "number", "26"),
                new("target_quality", "目标质量", "number", "92"),
                new("output", "输出 JSON", "text", "ai_training/process_optimization/outputs/platform_recommendation.json"),
                new("candidates", "搜索候选数", "number", "1200")
            ]),
        new(
            "equipment.train_fault",
            "故障预测训练",
            "Equipment",
            "用传感器 CSV 训练设备故障风险模型。",
            [
                new("data", "训练 CSV", "text", "ai_training/equipment/data/equipment_sensor_data.csv"),
                new("output", "模型输出目录", "text", "ai_training/equipment/outputs/platform_fault_model"),
                new("epochs", "训练轮数", "number", "300")
            ]),
        new(
            "equipment.predict_fault",
            "故障风险预测",
            "Equipment",
            "用已训练模型输出 fault_risk 和 predicted_fault。",
            [
                new("model_dir", "模型目录", "text", "ai_training/equipment/outputs/fault_model"),
                new("data", "传感器 CSV", "text", "ai_training/equipment/data/equipment_sensor_data.csv"),
                new("output", "预测 CSV", "text", "ai_training/equipment/outputs/platform_fault_predictions.csv")
            ]),
        new(
            "equipment.plot_risk",
            "设备风险趋势图",
            "Equipment",
            "把某台设备的故障风险按时间画成趋势图。",
            [
                new("predictions", "预测 CSV", "text", "ai_training/equipment/outputs/fault_predictions.csv"),
                new("equipment_id", "设备编号", "text", "pump_01"),
                new("output", "输出图片", "text", "ai_training/equipment/outputs/platform_risk_trend.jpg"),
                new("max_points", "最大点数", "number", "240")
            ]),
        new(
            "equipment.make_data",
            "生成设备模拟数据",
            "Equipment",
            "生成温度、振动、电流、压力、转速等模拟传感器数据。",
            [
                new("output", "输出 CSV", "text", "ai_training/equipment/data/platform_equipment.csv"),
                new("equipment_count", "设备数量", "number", "4"),
                new("hours", "小时数", "number", "240")
            ]),
        new(
            "process.train",
            "工艺模型训练",
            "Process",
            "训练质量、能耗、缺陷率预测模型。",
            [
                new("data", "工艺 CSV", "text", "ai_training/process_optimization/data/process_data.csv"),
                new("output", "模型输出目录", "text", "ai_training/process_optimization/outputs/platform_process_models")
            ]),
        new(
            "process.plot_candidates",
            "工艺候选对比图",
            "Process",
            "把工艺优化的候选方案画成质量、能耗、缺陷率对比图。",
            [
                new("recommendation", "推荐 JSON", "text", "ai_training/process_optimization/outputs/recommendation.json"),
                new("output", "输出图片", "text", "ai_training/process_optimization/outputs/platform_candidate_comparison.jpg"),
                new("top_n", "候选数量", "number", "6")
            ]),
        new(
            "process.make_data",
            "生成工艺模拟数据",
            "Process",
            "生成工艺参数优化所需的模拟历史数据。",
            [
                new("output", "输出 CSV", "text", "ai_training/process_optimization/data/platform_process.csv"),
                new("rows", "数据行数", "number", "3000")
            ])
    ];
}
