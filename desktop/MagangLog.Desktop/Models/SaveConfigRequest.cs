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
/// DTO for LLM settings matching backend LLMSettings.
/// </summary>
public class LlmSettingsDto
{
    [JsonPropertyName("provider")]
    public string Provider { get; set; } = "gemini";

    [JsonPropertyName("model")]
    public string Model { get; set; } = "gemini-3.5-flash";

    [JsonPropertyName("api_key")]
    public string ApiKey { get; set; } = string.Empty;

    [JsonPropertyName("temperature")]
    public double Temperature { get; set; } = 0.2;

    [JsonPropertyName("max_input_tokens")]
    public int MaxInputTokens { get; set; } = 6000;

    [JsonPropertyName("daily_token_budget")]
    public int DailyTokenBudget { get; set; } = 20000;
}

/// <summary>
/// DTO for notification settings matching backend NotifySettings.
/// </summary>
public class NotifySettingsDto
{
    [JsonPropertyName("channels")]
    public List<string> Channels { get; set; } = new() { "toast" };

    [JsonPropertyName("notify_on_success")]
    public bool NotifyOnSuccess { get; set; } = false;
}

/// <summary>
/// DTO for portal settings matching backend PortalSettings.
/// </summary>
public class PortalSettingsDto
{
    [JsonPropertyName("base_url")]
    public string BaseUrl { get; set; } = "https://monev.maganghub.kemnaker.go.id/dashboard/riwayat";

    [JsonPropertyName("auth_state")]
    public string AuthState { get; set; } = "data/auth/state.json";

    [JsonPropertyName("headless")]
    public bool Headless { get; set; } = true;
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

    [JsonPropertyName("llm")]
    public LlmSettingsDto Llm { get; set; } = new();

    [JsonPropertyName("notify")]
    public NotifySettingsDto Notify { get; set; } = new();

    [JsonPropertyName("portal")]
    public PortalSettingsDto Portal { get; set; } = new();

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
