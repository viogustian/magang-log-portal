using System.Drawing;
using System.Text.Json;
using MagangLog.Desktop.Models;
using Xunit;

namespace MagangLog.Desktop.Tests;

public class DraftEditorLogicTests
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true
    };

    [Theory]
    [InlineData(0, 255, 0, 0)]          // Red
    [InlineData(50, 255, 0, 0)]         // Red
    [InlineData(99, 255, 0, 0)]         // Red
    [InlineData(100, 0, 128, 0)]        // Green
    [InlineData(2500, 0, 128, 0)]       // Green
    [InlineData(4900, 0, 128, 0)]       // Green
    [InlineData(4901, 255, 69, 0)]      // OrangeRed
    [InlineData(5000, 255, 69, 0)]      // OrangeRed
    public void TestCharacterCounterColorThresholds(int charCount, int r, int g, int b)
    {
        var expectedColor = Color.FromArgb(r, g, b);
        var actualColor = CharacterCounterHelper.GetCharacterCountColor(charCount);
        Assert.Equal(expectedColor.ToArgb(), actualColor.ToArgb());
    }

    [Fact]
    public void TestCharacterCounterFormatting()
    {
        var text = CharacterCounterHelper.GetCharacterCountText(145);
        Assert.Equal("(145/5000 karakter)", text);
    }

    [Fact]
    public void TestCanApproveValidation()
    {
        var validText = new string('A', 120);
        var shortText = new string('B', 90);

        Assert.True(CharacterCounterHelper.CanApprove(validText, validText, validText));
        Assert.False(CharacterCounterHelper.CanApprove(shortText, validText, validText));
        Assert.False(CharacterCounterHelper.CanApprove(validText, shortText, validText));
        Assert.False(CharacterCounterHelper.CanApprove(validText, validText, shortText));
        Assert.False(CharacterCounterHelper.CanApprove("", "", ""));
    }

    [Fact]
    public void TestParseEntryDetailResponseFromJson()
    {
        var json = """
        {
            "entry_id": "entry-2026-11-10",
            "work_date": "2026-11-10",
            "kehadiran": "Hadir",
            "aktivitas": "Mengembangkan antarmuka draf logbook harian untuk peserta magang.",
            "pembelajaran": "Memahami arsitektur event-driven WinForms dan .NET 8.",
            "kendala": "Tidak ada kendala berarti selama proses pengembangan.",
            "status": "DRAFTED",
            "evidence_refs": {
                "git": ["commit-1", "commit-2"]
            },
            "validation_passed": true,
            "validation_errors": []
        }
        """;

        var response = JsonSerializer.Deserialize<EntryDetailResponse>(json, JsonOptions);

        Assert.NotNull(response);
        Assert.Equal("entry-2026-11-10", response.EntryId);
        Assert.Equal("2026-11-10", response.WorkDate);
        Assert.Equal("Hadir", response.Kehadiran);
        Assert.StartsWith("Mengembangkan", response.Aktivitas);
        Assert.True(response.ValidationPassed);
        Assert.Empty(response.ValidationErrors);
        Assert.Single(response.EvidenceRefs);
    }

    [Fact]
    public void TestSerializeEditEntryRequest()
    {
        var req = new EditEntryRequest
        {
            WorkDate = "2026-11-10",
            Kehadiran = "Hadir",
            Aktivitas = new string('A', 150),
            Pembelajaran = new string('B', 150),
            Kendala = new string('C', 150)
        };

        var json = JsonSerializer.Serialize(req, JsonOptions);
        Assert.Contains("\"kehadiran\":\"Hadir\"", json);
        Assert.Contains("\"work_date\":\"2026-11-10\"", json);
    }
}
