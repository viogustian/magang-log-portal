using System.Text.Json.Serialization;

namespace MagangLog.Desktop.Models;

public enum DashboardMode
{
    DraftEditor,
    FallbackNote
}

public class CreateNoteRequest
{
    [JsonPropertyName("work_date")]
    public string WorkDate { get; set; } = string.Empty;

    [JsonPropertyName("category")]
    public string Category { get; set; } = "aktivitas";

    [JsonPropertyName("note")]
    public string Note { get; set; } = string.Empty;

    [JsonPropertyName("db")]
    public string? Db { get; set; }
}

public class CreateNoteResponse
{
    [JsonPropertyName("success")]
    public bool Success { get; set; }

    [JsonPropertyName("note_id")]
    public string NoteId { get; set; } = string.Empty;

    [JsonPropertyName("created_at")]
    public string CreatedAt { get; set; } = string.Empty;
}

public static class DashboardModeResolver
{
    public static DashboardMode ResolveMode(TodayStatusResponse? status, EntryDetailResponse? entry = null)
    {
        // If an intern already drafted content or entry is loaded with text, prioritize DraftEditor
        if (entry != null && !string.IsNullOrWhiteSpace(entry.Aktivitas))
        {
            return DashboardMode.DraftEditor;
        }

        // When status is PERLU_INPUT or GATED (no evidence / needs input), activate FallbackNote
        if (status != null && (status.Status == "PERLU_INPUT" || status.Status == "GATED"))
        {
            return DashboardMode.FallbackNote;
        }

        return DashboardMode.DraftEditor;
    }
}

public static class FallbackNoteHelper
{
    public static bool IsValidNote(string? note)
    {
        if (string.IsNullOrWhiteSpace(note))
        {
            return false;
        }

        var trimmed = note.Trim();
        return trimmed.Length <= 5000;
    }
}
