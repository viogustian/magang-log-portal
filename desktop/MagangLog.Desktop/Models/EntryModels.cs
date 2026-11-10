using System.Drawing;
using System.Text.Json.Serialization;

namespace MagangLog.Desktop.Models;

/// <summary>
/// Detail of today's active logbook entry with validation status.
/// </summary>
public class EntryDetailResponse
{
    [JsonPropertyName("entry_id")]
    public string EntryId { get; set; } = string.Empty;

    [JsonPropertyName("work_date")]
    public string WorkDate { get; set; } = string.Empty;

    [JsonPropertyName("kehadiran")]
    public string Kehadiran { get; set; } = "Hadir";

    [JsonPropertyName("aktivitas")]
    public string Aktivitas { get; set; } = string.Empty;

    [JsonPropertyName("pembelajaran")]
    public string Pembelajaran { get; set; } = string.Empty;

    [JsonPropertyName("kendala")]
    public string Kendala { get; set; } = string.Empty;

    [JsonPropertyName("status")]
    public string Status { get; set; } = string.Empty;

    [JsonPropertyName("evidence_refs")]
    public Dictionary<string, List<string>> EvidenceRefs { get; set; } = new();

    [JsonPropertyName("validation_passed")]
    public bool ValidationPassed { get; set; }

    [JsonPropertyName("validation_errors")]
    public List<string> ValidationErrors { get; set; } = new();
}

/// <summary>
/// Payload to edit draft fields via POST /api/entry/edit.
/// </summary>
public class EditEntryRequest
{
    [JsonPropertyName("work_date")]
    public string? WorkDate { get; set; }

    [JsonPropertyName("kehadiran")]
    public string Kehadiran { get; set; } = "Hadir";

    [JsonPropertyName("aktivitas")]
    public string Aktivitas { get; set; } = string.Empty;

    [JsonPropertyName("pembelajaran")]
    public string Pembelajaran { get; set; } = string.Empty;

    [JsonPropertyName("kendala")]
    public string Kendala { get; set; } = string.Empty;
}

/// <summary>
/// Response after editing draft fields via POST /api/entry/edit.
/// </summary>
public class EditEntryResponse
{
    [JsonPropertyName("success")]
    public bool Success { get; set; }

    [JsonPropertyName("updated_entry")]
    public EntryDetailResponse? UpdatedEntry { get; set; }

    [JsonPropertyName("validation_passed")]
    public bool ValidationPassed { get; set; }

    [JsonPropertyName("validation_errors")]
    public List<string> ValidationErrors { get; set; } = new();
}

/// <summary>
/// Request to regenerate AI draft via POST /api/entry/draft.
/// </summary>
public class DraftEntryRequest
{
    [JsonPropertyName("work_date")]
    public string? WorkDate { get; set; }
}

/// <summary>
/// Response after regenerating AI draft via POST /api/entry/draft.
/// </summary>
public class DraftEntryResponse
{
    [JsonPropertyName("success")]
    public bool Success { get; set; }

    [JsonPropertyName("draft")]
    public EntryDetailResponse? Draft { get; set; }

    [JsonPropertyName("validation_passed")]
    public bool ValidationPassed { get; set; }

    [JsonPropertyName("validation_errors")]
    public List<string> ValidationErrors { get; set; } = new();
}

/// <summary>
/// Request to approve and submit validated draft via POST /api/entry/approve.
/// </summary>
public class ApproveEntryRequest
{
    [JsonPropertyName("work_date")]
    public string? WorkDate { get; set; }

    [JsonPropertyName("dry_run")]
    public bool DryRun { get; set; }
}

/// <summary>
/// Response after approving and submitting entry via POST /api/entry/approve.
/// </summary>
public class ApproveEntryResponse
{
    [JsonPropertyName("success")]
    public bool Success { get; set; }

    [JsonPropertyName("final_status")]
    public string FinalStatus { get; set; } = string.Empty;

    [JsonPropertyName("error_message")]
    public string? ErrorMessage { get; set; }
}

/// <summary>
/// Helper for calculating character counts, visual warning colors, and submission gate validation.
/// </summary>
public static class CharacterCounterHelper
{
    public static Color GetCharacterCountColor(int count)
    {
        if (count < 100)
        {
            return Color.Red;
        }

        if (count <= 4900)
        {
            return Color.Green;
        }

        return Color.OrangeRed;
    }

    public static string GetCharacterCountText(int count)
    {
        return $"({count}/5000 karakter)";
    }

    public static bool CanApprove(string? aktivitas, string? pembelajaran, string? kendala)
    {
        var lenAktivitas = (aktivitas ?? string.Empty).Trim().Length;
        var lenPembelajaran = (pembelajaran ?? string.Empty).Trim().Length;
        var lenKendala = (kendala ?? string.Empty).Trim().Length;

        return lenAktivitas >= 100 && lenAktivitas <= 5000 &&
               lenPembelajaran >= 100 && lenPembelajaran <= 5000 &&
               lenKendala >= 100 && lenKendala <= 5000;
    }
}
