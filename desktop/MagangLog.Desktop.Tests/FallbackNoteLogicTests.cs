using System.Text.Json;
using MagangLog.Desktop.Models;
using Xunit;

namespace MagangLog.Desktop.Tests;

public class FallbackNoteLogicTests
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true
    };

    [Theory]
    [InlineData("PERLU_INPUT", false, DashboardMode.FallbackNote)]
    [InlineData("GATED", false, DashboardMode.FallbackNote)]
    [InlineData("SIAP REVIEW", false, DashboardMode.DraftEditor)]
    [InlineData("BERHASIL", false, DashboardMode.DraftEditor)]
    [InlineData("SUDAH_TERKIRIM", false, DashboardMode.DraftEditor)]
    [InlineData("LIBUR", false, DashboardMode.DraftEditor)]
    [InlineData("PERLU_TINDAKAN", false, DashboardMode.DraftEditor)]
    public void TestResolveModeBasedOnStatus(string statusString, bool hasEntry, DashboardMode expectedMode)
    {
        var status = new TodayStatusResponse
        {
            TargetDate = "2026-11-10",
            Status = statusString,
            NeedsUserAction = true
        };

        var entry = hasEntry
            ? new EntryDetailResponse { Aktivitas = "Kegiatan magang terisi" }
            : null;

        var mode = DashboardModeResolver.ResolveMode(status, entry);
        Assert.Equal(expectedMode, mode);
    }

    [Fact]
    public void TestResolveModeWhenEntryAlreadyHasDraftEvenIfPerluInput()
    {
        var status = new TodayStatusResponse
        {
            TargetDate = "2026-11-10",
            Status = "PERLU_INPUT",
            NeedsUserAction = true
        };

        var entry = new EntryDetailResponse
        {
            Aktivitas = new string('A', 150),
            Pembelajaran = new string('B', 150),
            Kendala = new string('C', 150)
        };

        // If an intern already drafted content, keep DraftEditor accessible
        var mode = DashboardModeResolver.ResolveMode(status, entry);
        Assert.Equal(DashboardMode.DraftEditor, mode);
    }

    [Theory]
    [InlineData("", false)]
    [InlineData("   ", false)]
    [InlineData(null, false)]
    [InlineData("Melakukan diskusi dengan mentor", true)]
    public void TestNoteValidation(string? note, bool expectedValid)
    {
        var isValid = FallbackNoteHelper.IsValidNote(note);
        Assert.Equal(expectedValid, isValid);
    }

    [Fact]
    public void TestSerializeCreateNoteRequest()
    {
        var req = new CreateNoteRequest
        {
            WorkDate = "2026-11-10",
            Category = "aktivitas",
            Note = "Implementasi FallbackNotePanel pada LocalDashboard."
        };

        var json = JsonSerializer.Serialize(req, JsonOptions);
        Assert.Contains("\"work_date\":\"2026-11-10\"", json);
        Assert.Contains("\"category\":\"aktivitas\"", json);
        Assert.Contains("\"note\":", json);
    }

    [Fact]
    public void TestParseCreateNoteResponseFromJson()
    {
        var json = """
        {
            "success": true,
            "note_id": "note-1234",
            "created_at": "2026-11-10T10:00:00Z"
        }
        """;

        var res = JsonSerializer.Deserialize<CreateNoteResponse>(json, JsonOptions);
        Assert.NotNull(res);
        Assert.True(res.Success);
        Assert.Equal("note-1234", res.NoteId);
        Assert.Equal("2026-11-10T10:00:00Z", res.CreatedAt);
    }
}
