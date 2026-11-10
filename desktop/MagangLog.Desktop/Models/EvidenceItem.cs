using System.Drawing;
using System.Globalization;
using System.Text.Json.Serialization;

namespace MagangLog.Desktop.Models;

/// <summary>
/// Single immutable activity evidence item for today.
/// </summary>
public class EvidenceItem
{
    [JsonPropertyName("id")]
    public string Id { get; set; } = string.Empty;

    [JsonPropertyName("source")]
    public string Source { get; set; } = string.Empty;

    [JsonPropertyName("kind")]
    public string Kind { get; set; } = string.Empty;

    [JsonPropertyName("ts")]
    public string Timestamp { get; set; } = string.Empty;

    [JsonPropertyName("title")]
    public string Title { get; set; } = string.Empty;

    [JsonPropertyName("detail")]
    public string Detail { get; set; } = string.Empty;

    [JsonPropertyName("strength")]
    public string Strength { get; set; } = "weak";
}

/// <summary>
/// Response payload for GET /api/evidence/today.
/// </summary>
public class EvidenceFeedResponse
{
    [JsonPropertyName("items")]
    public List<EvidenceItem> Items { get; set; } = new();
}

/// <summary>
/// Helper utilities for formatting and filtering Evidence records.
/// </summary>
public static class EvidenceHelper
{
    public static readonly Color StrongColor = Color.FromArgb(200, 230, 200);
    public static readonly Color WeakColor = Color.FromArgb(255, 245, 200);

    public static string GetSourceBadge(string? source)
    {
        if (string.IsNullOrWhiteSpace(source))
        {
            return "📌 -";
        }

        var normalized = source.Trim().ToLowerInvariant();
        return normalized switch
        {
            "git" => "📦 Git",
            "app" => "💻 App",
            "browser" => "🌐 Browser",
            "notes" or "note" => "📝 Notes",
            _ => $"📌 {CultureInfo.InvariantCulture.TextInfo.ToTitleCase(normalized)}"
        };
    }

    public static string FormatTime(string? isoTimestamp)
    {
        if (string.IsNullOrWhiteSpace(isoTimestamp))
        {
            return "--:--";
        }

        if (DateTimeOffset.TryParse(isoTimestamp, CultureInfo.InvariantCulture, DateTimeStyles.None, out var dto))
        {
            return dto.ToLocalTime().ToString("HH:mm");
        }

        if (DateTime.TryParse(isoTimestamp, CultureInfo.InvariantCulture, DateTimeStyles.None, out var dt))
        {
            return dt.ToString("HH:mm");
        }

        return isoTimestamp;
    }

    public static List<EvidenceItem> FilterItems(IEnumerable<EvidenceItem> items, string? filterCategory)
    {
        if (items == null)
        {
            return new List<EvidenceItem>();
        }

        if (string.IsNullOrWhiteSpace(filterCategory) || filterCategory.Equals("Semua", StringComparison.OrdinalIgnoreCase))
        {
            return items.ToList();
        }

        var filter = filterCategory.Trim().ToLowerInvariant();

        return items.Where(item =>
        {
            var src = (item.Source ?? string.Empty).Trim().ToLowerInvariant();
            return filter switch
            {
                "git" => src == "git",
                "app" => src == "app",
                "browser" => src == "browser",
                "notes" => src is "notes" or "note",
                _ => src == filter
            };
        }).ToList();
    }

    public static Color GetStrengthColor(string? strength)
    {
        if (string.Equals(strength, "strong", StringComparison.OrdinalIgnoreCase))
        {
            return StrongColor;
        }

        return WeakColor;
    }
}
