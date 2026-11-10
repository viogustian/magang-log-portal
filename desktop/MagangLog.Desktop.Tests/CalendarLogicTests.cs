using System.Drawing;
using System.Text.Json;
using MagangLog.Desktop.Models;
using Xunit;

namespace MagangLog.Desktop.Tests;

public class CalendarLogicTests
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true
    };

    [Fact]
    public void TestOctober2026_StartsOnThursday_HasFiveRows()
    {
        // October 1, 2026 is Thursday (Column Index 3: Mon=0, Tue=1, Wed=2, Thu=3, Fri=4, Sat=5, Sun=6)
        var matrix = CalendarGridBuilder.BuildMonthMatrix(2026, 10);

        Assert.Equal(5, matrix.Count);

        // Row 0: Mon, Tue, Wed are blank padding
        Assert.Null(matrix[0][0].DayNumber);
        Assert.Null(matrix[0][1].DayNumber);
        Assert.Null(matrix[0][2].DayNumber);

        // Row 0, Col 3 is October 1st
        Assert.Equal(1, matrix[0][3].DayNumber);
        Assert.Equal("2026-10-01", matrix[0][3].DateString);
        Assert.Equal(3, matrix[0][3].DayOfWeekIndex);

        // Row 4, Col 5 is October 31st (Saturday)
        Assert.Equal(31, matrix[4][5].DayNumber);
        Assert.Equal("2026-10-31", matrix[4][5].DateString);

        // Row 4, Col 6 is Sunday (blank padding)
        Assert.Null(matrix[4][6].DayNumber);
    }

    [Fact]
    public void TestFebruary2026_StartsOnSunday_HasFiveRows()
    {
        // Feb 1, 2026 is Sunday (Col 6). Total 28 days.
        var matrix = CalendarGridBuilder.BuildMonthMatrix(2026, 2);

        Assert.Equal(5, matrix.Count);

        // First 6 days of row 0 are blank
        for (int i = 0; i < 6; i++)
        {
            Assert.Null(matrix[0][i].DayNumber);
        }

        // Sunday is Feb 1
        Assert.Equal(1, matrix[0][6].DayNumber);
        Assert.Equal("2026-02-01", matrix[0][6].DateString);

        // Feb 28 is Saturday (Col 5 of row 4)
        Assert.Equal(28, matrix[4][5].DayNumber);
        Assert.Equal("2026-02-28", matrix[4][5].DateString);
        Assert.Null(matrix[4][6].DayNumber);
    }

    [Fact]
    public void TestStatusMappingFromApiData()
    {
        var days = new List<CalendarDayInfo>
        {
            new() { Date = "2026-10-01", DayName = "Kamis", Status = "TERKIRIM" },
            new() { Date = "2026-10-02", DayName = "Jumat", Status = "PENDING" },
            new() { Date = "2026-10-03", DayName = "Sabtu", Status = "LIBUR" },
            new() { Date = "2026-10-04", DayName = "Minggu", Status = "LIBUR" },
            new() { Date = "2026-10-05", DayName = "Senin", Status = "TERKUNCI" }
        };

        var matrix = CalendarGridBuilder.BuildMonthMatrix(2026, 10, days);

        // Row 0 Col 3: Oct 1
        Assert.Equal("TERKIRIM", matrix[0][3].Status);

        // Row 0 Col 4: Oct 2
        Assert.Equal("PENDING", matrix[0][4].Status);

        // Row 0 Col 5: Oct 3
        Assert.Equal("LIBUR", matrix[0][5].Status);

        // Row 0 Col 6: Oct 4
        Assert.Equal("LIBUR", matrix[0][6].Status);

        // Row 1 Col 0: Oct 5
        Assert.Equal("TERKUNCI", matrix[1][0].Status);
    }

    [Theory]
    [InlineData("TERKIRIM", "LightGreen")]
    [InlineData("BERHASIL", "LightGreen")]
    [InlineData("PENDING", "LightGoldenrodYellow")]
    [InlineData("KOSONG", "LightGoldenrodYellow")]
    [InlineData("LIBUR", "LightGray")]
    [InlineData("TERKUNCI", "LightCoral")]
    [InlineData("UNKNOWN", "White")]
    public void TestCalendarColorMapping(string status, string expectedColorName)
    {
        var color = CalendarColorMapper.GetStatusColor(status);
        var expected = Color.FromName(expectedColorName);
        Assert.Equal(expected.ToArgb(), color.ToArgb());
    }

    [Fact]
    public void TestDeserializeMonthCalendarResponse()
    {
        var json = """
        {
            "days": [
                {
                    "date": "2026-10-01",
                    "day_name": "Kamis",
                    "status": "TERKIRIM",
                    "entry_id": "entry-2026-10-01"
                },
                {
                    "date": "2026-10-02",
                    "day_name": "Jumat",
                    "status": "PENDING",
                    "entry_id": null
                }
            ]
        }
        """;

        var res = JsonSerializer.Deserialize<MonthCalendarResponse>(json, JsonOptions);
        Assert.NotNull(res);
        Assert.Equal(2, res.Days.Count);
        Assert.Equal("2026-10-01", res.Days[0].Date);
        Assert.Equal("TERKIRIM", res.Days[0].Status);
        Assert.Equal("entry-2026-10-01", res.Days[0].EntryId);
    }
}
