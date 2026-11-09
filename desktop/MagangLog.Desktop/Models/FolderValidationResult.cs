using System.Text.Json.Serialization;

namespace MagangLog.Desktop.Models;

/// <summary>
/// Result of directory validation from POST /api/setup/validate-folders.
/// </summary>
public class FolderValidationResult
{
    [JsonPropertyName("path")]
    public string Path { get; set; } = string.Empty;

    [JsonPropertyName("exists")]
    public bool Exists { get; set; }

    [JsonPropertyName("readable")]
    public bool Readable { get; set; }

    [JsonPropertyName("is_git")]
    public bool IsGit { get; set; }

    [JsonPropertyName("error")]
    public string? Error { get; set; }

    [JsonIgnore]
    public bool IsValid => Exists && Readable;
}

public class ValidateFoldersRequest
{
    [JsonPropertyName("paths")]
    public List<string> Paths { get; set; } = new();
}

