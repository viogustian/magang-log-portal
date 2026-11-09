using System.Text.Json.Serialization;

namespace MagangLog.Desktop.Models;

/// <summary>
/// Configuration of active evidence sources based on Git usage frequency and explicit privacy consents.
/// </summary>
public class SourcesConfig
{
    [JsonPropertyName("git_frequency")]
    public string GitFrequency { get; set; } = "sering"; // "sering", "jarang", "tidak_sama_sekali"

    [JsonPropertyName("git_enabled")]
    public bool GitEnabled { get; set; } = true;

    [JsonPropertyName("app_enabled")]
    public bool AppEnabled { get; set; } = true;

    [JsonPropertyName("browser_enabled")]
    public bool BrowserEnabled { get; set; } = false;

    [JsonPropertyName("app_consent")]
    public bool AppConsent { get; set; } = true;

    [JsonPropertyName("browser_consent")]
    public bool BrowserConsent { get; set; } = false;
}
