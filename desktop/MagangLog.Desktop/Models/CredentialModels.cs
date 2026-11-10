using System.Text.Json.Serialization;

namespace MagangLog.Desktop.Models;

/// <summary>
/// Request payload for testing Gemini API Key.
/// </summary>
public class TestGeminiRequest
{
    [JsonPropertyName("api_key")]
    public string ApiKey { get; set; } = string.Empty;
}

/// <summary>
/// Response payload from testing Gemini API Key.
/// </summary>
public class TestGeminiResponse
{
    [JsonPropertyName("valid")]
    public bool Valid { get; set; }

    [JsonPropertyName("model")]
    public string Model { get; set; } = string.Empty;
}

/// <summary>
/// Response model for MagangHub portal authentication status.
/// </summary>
public class PortalAuthStatusResponse
{
    [JsonPropertyName("authenticated")]
    public bool Authenticated { get; set; }

    [JsonPropertyName("expires_at")]
    public string? ExpiresAt { get; set; }

    [JsonPropertyName("username")]
    public string? Username { get; set; }

    [JsonPropertyName("session_status")]
    public string SessionStatus { get; set; } = "missing"; // "active" | "expired" | "missing" | "invalid"
}

/// <summary>
/// Request payload for opening interactive login browser.
/// </summary>
public class OpenLoginRequest
{
    [JsonPropertyName("timeout_seconds")]
    public int TimeoutSeconds { get; set; } = 300;
}

/// <summary>
/// Response payload for interactive login browser launcher.
/// </summary>
public class OpenLoginResponse
{
    [JsonPropertyName("success")]
    public bool Success { get; set; }

    [JsonPropertyName("message")]
    public string Message { get; set; } = string.Empty;

    [JsonPropertyName("authenticated")]
    public bool Authenticated { get; set; }
}

/// <summary>
/// Individual model option returned from Google AI Studio.
/// </summary>
public class GeminiModelItem
{
    [JsonPropertyName("id")]
    public string Id { get; set; } = string.Empty;

    [JsonPropertyName("display_name")]
    public string DisplayName { get; set; } = string.Empty;

    [JsonPropertyName("is_recommended")]
    public bool IsRecommended { get; set; } = false;
}

/// <summary>
/// Response model for available live Gemini models.
/// </summary>
public class GeminiModelsResponse
{
    [JsonPropertyName("models")]
    public List<GeminiModelItem> Models { get; set; } = new();

    [JsonPropertyName("active_model")]
    public string ActiveModel { get; set; } = "gemini-3.5-flash";

    [JsonPropertyName("source")]
    public string Source { get; set; } = string.Empty;
}

