using System.Drawing;
using System.Text.Json.Serialization;

namespace MagangLog.Desktop.Models;

/// <summary>
/// Status category for local dashboard badge representation.
/// </summary>
public enum DashboardStatus
{
    Berhasil,
    SiapReview,
    PerluInput,
    Libur,
    PerluTindakan,
    Offline
}

/// <summary>
/// DTO model representing response from GET /api/status/today.
/// </summary>
public class TodayStatusResponse
{
    [JsonPropertyName("target_date")]
    public string TargetDate { get; set; } = string.Empty;

    [JsonPropertyName("status")]
    public string Status { get; set; } = string.Empty;

    [JsonPropertyName("is_workday")]
    public bool IsWorkday { get; set; }

    [JsonPropertyName("is_holiday")]
    public bool IsHoliday { get; set; }

    [JsonPropertyName("holiday_name")]
    public string? HolidayName { get; set; }

    [JsonPropertyName("has_submitted_entry")]
    public bool HasSubmittedEntry { get; set; }

    [JsonPropertyName("needs_user_action")]
    public bool NeedsUserAction { get; set; }
}

/// <summary>
/// Helper mapping backend status payloads to dashboard status categories, badge colors, and labels.
/// </summary>
public static class DashboardStatusHelper
{
    public static readonly Color GreenColor = Color.FromArgb(200, 230, 200);
    public static readonly Color BlueColor = Color.FromArgb(200, 210, 240);
    public static readonly Color YellowColor = Color.FromArgb(255, 245, 200);
    public static readonly Color GrayColor = Color.FromArgb(230, 230, 230);
    public static readonly Color RedColor = Color.FromArgb(255, 210, 210);

    public static DashboardStatus MapStatus(string? statusStr, bool hasSubmitted = false, bool isHoliday = false)
    {
        if (hasSubmitted)
        {
            return DashboardStatus.Berhasil;
        }

        if (isHoliday)
        {
            return DashboardStatus.Libur;
        }

        if (string.IsNullOrWhiteSpace(statusStr))
        {
            return DashboardStatus.PerluInput;
        }

        var normalized = statusStr.Trim().ToUpperInvariant();

        return normalized switch
        {
            "BERHASIL" or "SUDAH_TERKIRIM" or "TERKIRIM" => DashboardStatus.Berhasil,
            "SIAP REVIEW" or "SIAP_REVIEW" or "DRAFTED" or "PERLU_REVIEW" => DashboardStatus.SiapReview,
            "PERLU_INPUT" or "GATED" => DashboardStatus.PerluInput,
            "LIBUR" => DashboardStatus.Libur,
            "PERLU_TINDAKAN" or "ERROR" or "GAGAL" => DashboardStatus.PerluTindakan,
            _ => DashboardStatus.PerluTindakan
        };
    }

    public static Color GetBadgeColor(DashboardStatus status)
    {
        return status switch
        {
            DashboardStatus.Berhasil => GreenColor,
            DashboardStatus.SiapReview => BlueColor,
            DashboardStatus.PerluInput => YellowColor,
            DashboardStatus.Libur => GrayColor,
            DashboardStatus.PerluTindakan => RedColor,
            DashboardStatus.Offline => RedColor,
            _ => GrayColor
        };
    }

    public static string GetBadgeText(DashboardStatus status, string? holidayName = null)
    {
        return status switch
        {
            DashboardStatus.Berhasil => "🟢 BERHASIL",
            DashboardStatus.SiapReview => "🔵 SIAP REVIEW",
            DashboardStatus.PerluInput => "🟡 PERLU_INPUT",
            DashboardStatus.Libur => string.IsNullOrWhiteSpace(holidayName) ? "⚪ LIBUR" : $"⚪ LIBUR ({holidayName})",
            DashboardStatus.PerluTindakan => "🔴 PERLU_TINDAKAN",
            DashboardStatus.Offline => "⚠️ Backend tidak terhubung",
            _ => "⚪ STATUS TIDAK DIKETAHUI"
        };
    }
}
