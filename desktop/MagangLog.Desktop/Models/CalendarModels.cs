using System.Drawing;
using System.Text.Json.Serialization;

namespace MagangLog.Desktop.Models;

/// <summary>
/// Status description for a single day in the month calendar.
/// </summary>
public class CalendarDayInfo
{
    [JsonPropertyName("date")]
    public string Date { get; set; } = string.Empty;

    [JsonPropertyName("day_name")]
    public string DayName { get; set; } = string.Empty;

    [JsonPropertyName("status")]
    public string Status { get; set; } = "KOSONG";

    [JsonPropertyName("entry_id")]
    public string? EntryId { get; set; }
}

/// <summary>
/// Response payload for GET /api/calendar/month.
/// </summary>
public class MonthCalendarResponse
{
    [JsonPropertyName("days")]
    public List<CalendarDayInfo> Days { get; set; } = new();
}

/// <summary>
/// Model for a cell in the 7-column calendar matrix.
/// </summary>
public class CalendarDayCellModel
{
    public int? DayNumber { get; set; }
    public string? DateString { get; set; }
    public string? Status { get; set; }
    public int DayOfWeekIndex { get; set; } // 0: Sen, 1: Sel, 2: Rab, 3: Kam, 4: Jum, 5: Sab, 6: Min
    public bool IsCurrentMonth { get; set; }
    public bool IsToday { get; set; }
    public string? EntryId { get; set; }
}

/// <summary>
/// Status color mapper for calendar cells based on Kemnaker Monev compliance states.
/// </summary>
public static class CalendarColorMapper
{
    public static Color GetStatusColor(string? status)
    {
        if (string.IsNullOrWhiteSpace(status))
        {
            return Color.White;
        }

        return status.ToUpperInvariant() switch
        {
            "TERKIRIM" or "BERHASIL" => Color.LightGreen,
            "PENDING" or "KOSONG" => Color.LightGoldenrodYellow,
            "LIBUR" => Color.LightGray,
            "TERKUNCI" => Color.LightCoral,
            _ => Color.White
        };
    }
}

/// <summary>
/// Algorithmic builder that arranges days of a month into a 7-column weekly matrix (Mon to Sun).
/// </summary>
public static class CalendarGridBuilder
{
    public static List<CalendarDayCellModel[]> BuildMonthMatrix(
        int year,
        int month,
        IEnumerable<CalendarDayInfo>? dayInfos = null,
        DateTime? todayOverride = null)
    {
        var today = (todayOverride ?? DateTime.Today).ToString("yyyy-MM-dd");
        var dayInfoDict = dayInfos?.ToDictionary(d => d.Date, d => d) ?? new Dictionary<string, CalendarDayInfo>();

        var firstDayOfMonth = new DateTime(year, month, 1);
        var daysInMonth = DateTime.DaysInMonth(year, month);

        // DayOfWeek: Sunday = 0, Monday = 1, ..., Saturday = 6
        // Map to Monday-first: Mon = 0, Tue = 1, Wed = 2, Thu = 3, Fri = 4, Sat = 5, Sun = 6
        int startingCol = ((int)firstDayOfMonth.DayOfWeek + 6) % 7;

        var matrix = new List<CalendarDayCellModel[]>();
        var currentRow = new CalendarDayCellModel[7];

        for (int i = 0; i < 7; i++)
        {
            currentRow[i] = new CalendarDayCellModel
            {
                DayOfWeekIndex = i,
                IsCurrentMonth = false
            };
        }

        int currentDay = 1;
        int col = startingCol;

        while (currentDay <= daysInMonth)
        {
            var dateStr = $"{year:D4}-{month:D2}-{currentDay:D2}";
            dayInfoDict.TryGetValue(dateStr, out var info);

            currentRow[col] = new CalendarDayCellModel
            {
                DayNumber = currentDay,
                DateString = dateStr,
                Status = info?.Status,
                EntryId = info?.EntryId,
                DayOfWeekIndex = col,
                IsCurrentMonth = true,
                IsToday = string.Equals(dateStr, today, StringComparison.OrdinalIgnoreCase)
            };

            col++;
            if (col == 7)
            {
                matrix.Add(currentRow);
                currentRow = new CalendarDayCellModel[7];
                for (int i = 0; i < 7; i++)
                {
                    currentRow[i] = new CalendarDayCellModel
                    {
                        DayOfWeekIndex = i,
                        IsCurrentMonth = false
                    };
                }
                col = 0;
            }
            currentDay++;
        }

        if (col > 0)
        {
            matrix.Add(currentRow);
        }

        return matrix;
    }
}
