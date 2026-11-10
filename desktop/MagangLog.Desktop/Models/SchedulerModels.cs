using System.Text.Json.Serialization;

namespace MagangLog.Desktop.Models;

/// <summary>
/// Payload to register background automation in Windows Task Scheduler via POST /api/setup/register-scheduler.
/// </summary>
public class RegisterSchedulerRequest
{
    [JsonPropertyName("trigger_time")]
    public string? TriggerTime { get; set; }

    [JsonPropertyName("review_time")]
    public string ReviewTime { get; set; } = "16:30";

    [JsonPropertyName("resume_time")]
    public string ResumeTime { get; set; } = "20:00";

    [JsonPropertyName("active_days")]
    public List<string>? ActiveDays { get; set; }

    [JsonPropertyName("task_prefix")]
    public string TaskPrefix { get; set; } = "MagangLog";
}

/// <summary>
/// Response payload from POST /api/setup/register-scheduler.
/// </summary>
public class RegisterSchedulerResponse
{
    [JsonPropertyName("success")]
    public bool Success { get; set; }

    [JsonPropertyName("task_name")]
    public string TaskName { get; set; } = string.Empty;

    [JsonPropertyName("review_time")]
    public string ReviewTime { get; set; } = "16:30";

    [JsonPropertyName("resume_time")]
    public string ResumeTime { get; set; } = "20:00";
}

/// <summary>
/// Response payload for GET /api/setup/scheduler-status.
/// </summary>
public class SchedulerStatusResponse
{
    [JsonPropertyName("status")]
    public string Status { get; set; } = "unregistered"; // registered | needs_update | unregistered

    [JsonPropertyName("is_registered")]
    public bool IsRegistered { get; set; }

    [JsonPropertyName("review_task_name")]
    public string ReviewTaskName { get; set; } = "MagangLog-Review";

    [JsonPropertyName("resume_task_name")]
    public string ResumeTaskName { get; set; } = "MagangLog-Resume";

    [JsonPropertyName("review_time")]
    public string? ReviewTime { get; set; }

    [JsonPropertyName("resume_time")]
    public string? ResumeTime { get; set; }

    [JsonPropertyName("diagnostic_message")]
    public string DiagnosticMessage { get; set; } = string.Empty;
}

/// <summary>
/// Payload to unregister background tasks via POST /api/setup/unregister-scheduler.
/// </summary>
public class UnregisterSchedulerRequest
{
    [JsonPropertyName("task_prefix")]
    public string TaskPrefix { get; set; } = "MagangLog";
}

/// <summary>
/// Response payload from POST /api/setup/unregister-scheduler.
/// </summary>
public class UnregisterSchedulerResponse
{
    [JsonPropertyName("success")]
    public bool Success { get; set; }

    [JsonPropertyName("message")]
    public string Message { get; set; } = string.Empty;
}
