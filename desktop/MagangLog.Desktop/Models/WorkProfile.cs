using System.Text.Json.Serialization;

namespace MagangLog.Desktop.Models;

/// <summary>
/// Configuration for an individual desktop application within a WorkProfile.
/// </summary>
public class ApplicationConfig
{
    [JsonPropertyName("name")]
    public string Name { get; set; } = string.Empty;

    [JsonPropertyName("process_names")]
    public List<string> ProcessNames { get; set; } = new();

    [JsonPropertyName("file_extensions")]
    public List<string> FileExtensions { get; set; } = new();

    [JsonPropertyName("log_patterns")]
    public List<string> LogPatterns { get; set; } = new();
}

/// <summary>
/// Domain model for intern WorkProfile describing role, applications, and browser domains.
/// </summary>
public class WorkProfile
{
    [JsonPropertyName("profile_name")]
    public string ProfileName { get; set; } = string.Empty;

    [JsonPropertyName("natural_description")]
    public string NaturalDescription { get; set; } = string.Empty;

    [JsonPropertyName("applications")]
    public List<ApplicationConfig> Applications { get; set; } = new();

    [JsonPropertyName("browser_domains")]
    public List<string> BrowserDomains { get; set; } = new();

    [JsonPropertyName("watch_folders")]
    public List<string> WatchFolders { get; set; } = new();

    /// <summary>
    /// Extracts a consolidated, deduplicated list of detection keywords (executable process names and app names).
    /// </summary>
    public List<string> ExtractKeywords()
    {
        var keywords = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var app in Applications)
        {
            if (!string.IsNullOrWhiteSpace(app.Name))
            {
                keywords.Add(app.Name.Trim());
            }
            foreach (var proc in app.ProcessNames)
            {
                if (!string.IsNullOrWhiteSpace(proc))
                {
                    keywords.Add(proc.Trim());
                }
            }
        }
        return keywords.ToList();
    }
}

/// <summary>
/// Request payload for predicting a WorkProfile from a task description.
/// </summary>
public class PredictProfileRequest
{
    [JsonPropertyName("description")]
    public string Description { get; set; } = string.Empty;

    [JsonPropertyName("api_key")]
    public string ApiKey { get; set; } = string.Empty;
}

/// <summary>
/// Response payload from profile prediction containing source and predicted profile.
/// </summary>
public class PredictProfileResponse
{
    [JsonPropertyName("source")]
    public string Source { get; set; } = "gemini"; // "gemini" | "preset_fallback"

    [JsonPropertyName("profile")]
    public WorkProfile Profile { get; set; } = new();
}

