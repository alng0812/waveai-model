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
var uploadData = Path.Combine(workspaceRoot, "platform_data", "uploads");
var pythonExe = Environment.GetEnvironmentVariable("AI_PLATFORM_PYTHON")
    ?? @"C:\Users\86180\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe";

Directory.CreateDirectory(platformData);
Directory.CreateDirectory(uploadData);

var jsonOptions = new JsonSerializerOptions
{
    PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
    WriteIndented = true,
    DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull
};

app.UseDefaultFiles();
app.UseStaticFiles();

app.MapGet("/api/modules", () => Results.Json(ModuleCatalog.All, jsonOptions));

app.MapPost("/api/uploads/csv", async (HttpRequest request) =>
{
    if (!request.HasFormContentType)
    {
        return Results.BadRequest(new { error = "multipart form data is required" });
    }

    var form = await request.ReadFormAsync();
    var file = form.Files["file"];
    var task = form["task"].ToString();
    var fieldName = form["fieldName"].ToString();
    if (file is null || file.Length == 0)
    {
        return Results.BadRequest(new { error = "csv file is required" });
    }

    var extension = Path.GetExtension(file.FileName).ToLowerInvariant();
    if (extension != ".csv")
    {
        return Results.BadRequest(new { error = "only .csv files are supported" });
    }

    const long maxUploadBytes = 50L * 1024 * 1024;
    if (file.Length > maxUploadBytes)
    {
        return Results.BadRequest(new { error = "csv file is too large", maxMb = 50 });
    }

    var originalName = Path.GetFileName(file.FileName);
    var safeName = MakeSafeFileName(Path.GetFileNameWithoutExtension(originalName));
    var suffix = Guid.NewGuid().ToString("N")[..8];
    var storedName = $"{DateTime.Now:yyyyMMdd_HHmmss}_{safeName}_{suffix}.csv";
    var fullPath = Path.Combine(uploadData, storedName);

    await using (var stream = File.Create(fullPath))
    {
        await file.CopyToAsync(stream);
    }

    var profile = ReadCsvProfile(fullPath);
    var validation = ValidateCsv(task, fieldName, profile.Columns);
    var relativePath = ToRelativePath(workspaceRoot, fullPath);
    return Results.Json(new
    {
        originalName,
        path = relativePath,
        sizeBytes = file.Length,
        profile.Columns,
        profile.Rows,
        profile.Preview,
        validation
    }, jsonOptions);
});

app.MapPost("/api/uploads/csv/map", async (CsvMapRequest request) =>
{
    if (string.IsNullOrWhiteSpace(request.Path))
    {
        return Results.BadRequest(new { error = "path is required" });
    }

    var sourcePath = ResolveWorkspacePath(workspaceRoot, request.Path);
    if (!File.Exists(sourcePath))
    {
        return Results.NotFound(new { error = "csv file not found" });
    }

    if (Path.GetExtension(sourcePath).ToLowerInvariant() != ".csv")
    {
        return Results.BadRequest(new { error = "only .csv files are supported" });
    }

    var lines = await File.ReadAllLinesAsync(sourcePath);
    if (lines.Length == 0)
    {
        return Results.BadRequest(new { error = "csv file is empty" });
    }

    var headers = SplitCsvLine(lines[0]).ToArray();
    var mappings = request.Mappings ?? new Dictionary<string, string>();
    var missingSources = mappings.Values
        .Where(value => !string.IsNullOrWhiteSpace(value))
        .Where(value => !headers.Any(header => SameColumn(header, value)))
        .Distinct(StringComparer.OrdinalIgnoreCase)
        .ToArray();
    if (missingSources.Length > 0)
    {
        return Results.BadRequest(new { error = "mapped source columns not found", missingSources });
    }

    var renamedHeaders = headers.Select(header =>
    {
        var target = mappings.FirstOrDefault(pair => SameColumn(pair.Value, header)).Key;
        return string.IsNullOrWhiteSpace(target) ? header : target;
    }).ToArray();

    var suffix = Guid.NewGuid().ToString("N")[..8];
    var mappedName = $"{Path.GetFileNameWithoutExtension(sourcePath)}_mapped_{suffix}.csv";
    var mappedPath = Path.Combine(uploadData, mappedName);
    var mappedLines = new List<string> { ToCsvLine(renamedHeaders) };
    mappedLines.AddRange(lines.Skip(1));
    await File.WriteAllLinesAsync(mappedPath, mappedLines);

    var profile = ReadCsvProfile(mappedPath);
    var validation = ValidateCsv(request.Task, request.FieldName, profile.Columns);
    var relativePath = ToRelativePath(workspaceRoot, mappedPath);
    return Results.Json(new
    {
        path = relativePath,
        profile.Columns,
        profile.Rows,
        profile.Preview,
        validation
    }, jsonOptions);
});

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

static string MakeSafeFileName(string value)
{
    var invalid = Path.GetInvalidFileNameChars();
    var chars = value
        .Select(ch => invalid.Contains(ch) || char.IsWhiteSpace(ch) ? '_' : ch)
        .ToArray();
    var safe = new string(chars).Trim('_');
    return string.IsNullOrWhiteSpace(safe) ? "upload" : safe[..Math.Min(safe.Length, 48)];
}

static CsvProfile ReadCsvProfile(string path)
{
    var preview = File.ReadLines(path).Take(6).ToArray();
    var columns = preview.Length == 0 ? [] : SplitCsvLine(preview[0]).ToArray();
    var rows = Math.Max(0, File.ReadLines(path).LongCount() - 1);
    return new CsvProfile(columns, rows, preview);
}

static CsvValidation ValidateCsv(string? task, string? fieldName, string[] columns)
{
    var schema = FindCsvSchema(task, fieldName);
    if (schema is null)
    {
        return new CsvValidation([], [], [], true, new Dictionary<string, string>(), "此字段没有配置固定列名规则。");
    }

    var missing = schema.Required
        .Where(required => !columns.Any(column => SameColumn(column, required)))
        .ToArray();
    var suggested = missing
        .Select(required => new { Required = required, Source = FindSuggestedColumn(required, columns) })
        .Where(item => item.Source is not null)
        .ToDictionary(item => item.Required, item => item.Source!, StringComparer.OrdinalIgnoreCase);
    var usable = missing.Length == 0;
    var message = usable
        ? "CSV 字段完整，可以用于当前任务。"
        : $"缺少 {missing.Length} 个字段，可先做字段映射。";
    return new CsvValidation(schema.Required, schema.Optional, missing, usable, suggested, message);
}

static CsvSchema? FindCsvSchema(string? task, string? fieldName)
{
    var key = $"{task}:{fieldName}".ToLowerInvariant();
    return key switch
    {
        "equipment.train_fault:data" => new CsvSchema(
            ["temperature", "vibration", "current", "pressure", "rpm", "load", "fault_within_24h"],
            ["timestamp", "equipment_id", "anomaly"]),
        "equipment.predict_fault:data" => new CsvSchema(
            ["temperature", "vibration", "current", "pressure", "rpm", "load"],
            ["timestamp", "equipment_id"]),
        "equipment.plot_risk:predictions" => new CsvSchema(
            ["timestamp", "equipment_id", "fault_risk"],
            ["predicted_fault", "anomaly_score", "predicted_anomaly"]),
        "process.train:data" => new CsvSchema(
            [
                "material_moisture", "material_grade", "ambient_temp", "target_quality",
                "set_temperature", "set_pressure", "set_flow_rate", "line_speed",
                "quality_score", "energy_consumption", "defect_rate"
            ],
            []),
        _ => null
    };
}

static string? FindSuggestedColumn(string required, string[] columns)
{
    if (CsvRules.ColumnAliases.TryGetValue(required, out var aliases))
    {
        var match = columns.FirstOrDefault(column => aliases.Any(alias => SameColumn(column, alias)));
        if (match is not null) return match;
    }

    var normalizedRequired = NormalizeColumn(required);
    return columns.FirstOrDefault(column =>
        NormalizeColumn(column).Contains(normalizedRequired, StringComparison.OrdinalIgnoreCase) ||
        normalizedRequired.Contains(NormalizeColumn(column), StringComparison.OrdinalIgnoreCase));
}

static bool SameColumn(string? left, string? right) =>
    NormalizeColumn(left) == NormalizeColumn(right);

static string NormalizeColumn(string? value) =>
    new((value ?? "")
        .Trim()
        .ToLowerInvariant()
        .Where(ch => char.IsLetterOrDigit(ch) || ch is '_' or '-')
        .ToArray());

static IEnumerable<string> SplitCsvLine(string line)
{
    var cells = new List<string>();
    var current = new System.Text.StringBuilder();
    var inQuotes = false;

    for (var i = 0; i < line.Length; i++)
    {
        var ch = line[i];
        if (ch == '"')
        {
            if (inQuotes && i + 1 < line.Length && line[i + 1] == '"')
            {
                current.Append('"');
                i++;
            }
            else
            {
                inQuotes = !inQuotes;
            }
        }
        else if (ch == ',' && !inQuotes)
        {
            cells.Add(current.ToString());
            current.Clear();
        }
        else
        {
            current.Append(ch);
        }
    }

    cells.Add(current.ToString());
    return cells;
}

static string ToCsvLine(IEnumerable<string> cells) =>
    string.Join(",", cells.Select(cell =>
    {
        var value = cell ?? "";
        return value.Contains(',') || value.Contains('"') || value.Contains('\n')
            ? $"\"{value.Replace("\"", "\"\"")}\""
            : value;
    }));

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

record CsvMapRequest(string Path, string? Task, string? FieldName, Dictionary<string, string>? Mappings);

record TaskResultFile(
    string TaskId,
    string Task,
    string Status,
    [property: JsonPropertyName("result_path")] string? ResultPath
);

record CsvProfile(string[] Columns, long Rows, string[] Preview);

record CsvSchema(string[] Required, string[] Optional);

record CsvValidation(
    string[] Required,
    string[] Optional,
    string[] Missing,
    bool Usable,
    Dictionary<string, string> SuggestedMappings,
    string Message
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

static class CsvRules
{
    public static readonly Dictionary<string, string[]> ColumnAliases = new(StringComparer.OrdinalIgnoreCase)
    {
        ["timestamp"] = ["time", "datetime", "date", "采集时间", "时间", "日期"],
        ["equipment_id"] = ["device_id", "machine_id", "asset_id", "设备编号", "设备id", "设备"],
        ["temperature"] = ["temp", "温度", "设备温度"],
        ["vibration"] = ["vib", "振动", "震动", "振动值"],
        ["current"] = ["amp", "amps", "电流"],
        ["pressure"] = ["press", "压力"],
        ["rpm"] = ["speed", "rotate_speed", "转速"],
        ["load"] = ["负载", "载荷", "工况负载"],
        ["fault_within_24h"] = ["fault", "label", "target", "故障", "是否故障", "24小时内故障"],
        ["fault_risk"] = ["risk", "score", "故障风险", "风险分"],
        ["predicted_fault"] = ["fault_prediction", "预测故障", "故障预测"],
        ["material_moisture"] = ["moisture", "原料水分", "水分"],
        ["material_grade"] = ["grade", "原料等级", "等级"],
        ["ambient_temp"] = ["ambient_temperature", "环境温度"],
        ["target_quality"] = ["target", "目标质量", "目标分"],
        ["set_temperature"] = ["process_temperature", "工艺温度", "设定温度"],
        ["set_pressure"] = ["process_pressure", "工艺压力", "设定压力"],
        ["set_flow_rate"] = ["flow", "flow_rate", "流量", "设定流量"],
        ["line_speed"] = ["speed", "线速", "产线速度"],
        ["quality_score"] = ["quality", "质量", "质量分"],
        ["energy_consumption"] = ["energy", "能耗", "能源消耗"],
        ["defect_rate"] = ["defect", "缺陷率", "不良率"]
    };
}
