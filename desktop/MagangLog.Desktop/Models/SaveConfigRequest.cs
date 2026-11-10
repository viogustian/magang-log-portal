using System.Text.Json.Serialization;

namespace MagangLog.Desktop.Models;

/// <summary>
/// DTO for review configuration matching backend ReviewSettings.
/// </summary>
public class ReviewSettingsDto
{
    [JsonPropertyName("mode")]
    public string Mode { get; set; } = "review";

    [JsonPropertyName("auto_if_confident")]
    public bool AutoIfConfident { get; set; } = false;
}

/// <summary>
/// DTO for Git source settings matching backend GitSourceSettings.
/// </summary>
public class GitSourceSettingsDto
{
    [JsonPropertyName("enabled")]
    public bool Enabled { get; set; } = true;

    [JsonPropertyName("repositories")]
    public List<string> Repositories { get; set; } = new();
}

/// <summary>
/// DTO for browser source settings matching backend BrowserSourceSettings.
/// </summary>
public class BrowserSourceSettingsDto
{
    [JsonPropertyName("enabled")]
    public bool Enabled { get; set; } = false;

    [JsonPropertyName("allow_domains")]
    public List<string> AllowDomains { get; set; } = new();
}

/// <summary>
/// DTO for app source settings matching backend AppSourceSettings.
/// </summary>
public class AppSourceSettingsDto
{
    [JsonPropertyName("enabled")]
    public bool Enabled { get; set; } = true;

    [JsonPropertyName("work_profile")]
    public WorkProfile? WorkProfile { get; set; }
}

/// <summary>
/// DTO for sources configuration matching backend SourcesSettings.
/// </summary>
public class SourcesSettingsDto
{
    [JsonPropertyName("git")]
    public GitSourceSettingsDto Git { get; set; } = new();

    [JsonPropertyName("browser")]
    public BrowserSourceSettingsDto Browser { get; set; } = new();

    [JsonPropertyName("app")]
    public AppSourceSettingsDto App { get; set; } = new();
}

/// <summary>
/// Unified save request payload conforming to backend POST /api/setup/save.
/// </summary>
public class SaveConfigRequest
{
    [JsonPropertyName("timezone")]
    public string Timezone { get; set; } = "Asia/Jakarta";

    [JsonPropertyName("workdays")]
    public List<string> Workdays { get; set; } = new() { "mon", "tue", "wed", "thu", "fri" };

    [JsonPropertyName("review")]
    public ReviewSettingsDto Review { get; set; } = new();

    [JsonPropertyName("sources")]
    public SourcesSettingsDto Sources { get; set; } = new();

    [JsonPropertyName("work_profile")]
    public WorkProfile? WorkProfile { get; set; }

    [JsonPropertyName("config_path")]
    public string? ConfigPath { get; set; }
}

/// <summary>
/// Response payload from POST /api/setup/save.
/// </summary>
public class SaveConfigResponse
{
    [JsonPropertyName("success")]
    public bool Success { get; set; }

    [JsonPropertyName("saved_at")]
    public string SavedAt { get; set; } = string.Empty;
}
