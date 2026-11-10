using System.Text.Json.Serialization;

namespace MagangLog.Desktop.Models;

/// <summary>
/// Structured Windows-specific installation guidance and troubleshooting steps.
/// </summary>
public class InstallationGuidance
{
    [JsonPropertyName("download_url")]
    public string DownloadUrl { get; set; } = string.Empty;

    [JsonPropertyName("install_steps")]
    public List<string> InstallSteps { get; set; } = new();

    [JsonPropertyName("verification_command")]
    public string VerificationCommand { get; set; } = string.Empty;

    [JsonPropertyName("expected_output")]
    public string ExpectedOutput { get; set; } = string.Empty;

    [JsonPropertyName("troubleshooting")]
    public List<string> Troubleshooting { get; set; } = new();
}

/// <summary>
/// Status and metadata for a host system requirement.
/// </summary>
public class RequirementItem
{
    [JsonPropertyName("name")]
    public string Name { get; set; } = string.Empty;

    [JsonPropertyName("min_version")]
    public string MinVersion { get; set; } = string.Empty;

    [JsonPropertyName("installed_version")]
    public string? InstalledVersion { get; set; }

    [JsonPropertyName("status")]
    public string Status { get; set; } = "missing"; // "ok", "version_mismatch", "missing"

    [JsonPropertyName("guidance")]
    public InstallationGuidance Guidance { get; set; } = new();
}

public class RecheckRequirementRequest
{
    [JsonPropertyName("name")]
    public string Name { get; set; } = string.Empty;
}

