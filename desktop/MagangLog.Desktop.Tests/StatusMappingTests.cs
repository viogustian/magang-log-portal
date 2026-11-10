using System.Drawing;
using System.Text.Json;
using MagangLog.Desktop.Models;
using Xunit;

namespace MagangLog.Desktop.Tests;

public class StatusMappingTests
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true
    };

    [Fact]
    public void TestParseTodayStatusResponseFromJson()
    {
        var json = """
        {
            "target_date": "2026-11-10",
            "status": "SUDAH_TERKIRIM",
            "is_workday": true,
            "is_holiday": false,
            "holiday_name": null,
            "has_submitted_entry": true,
            "needs_user_action": false
        }
        """;

        var response = JsonSerializer.Deserialize<TodayStatusResponse>(json, JsonOptions);

        Assert.NotNull(response);
        Assert.Equal("2026-11-10", response.TargetDate);
        Assert.Equal("SUDAH_TERKIRIM", response.Status);
        Assert.True(response.IsWorkday);
        Assert.False(response.IsHoliday);
        Assert.Null(response.HolidayName);
        Assert.True(response.HasSubmittedEntry);
        Assert.False(response.NeedsUserAction);
    }

    [Theory]
    [InlineData("BERHASIL", false, false, DashboardStatus.Berhasil, "🟢 BERHASIL")]
    [InlineData("SUDAH_TERKIRIM", true, false, DashboardStatus.Berhasil, "🟢 BERHASIL")]
    [InlineData("TERKIRIM", false, false, DashboardStatus.Berhasil, "🟢 BERHASIL")]
    [InlineData("SIAP REVIEW", false, false, DashboardStatus.SiapReview, "🔵 SIAP REVIEW")]
    [InlineData("SIAP_REVIEW", false, false, DashboardStatus.SiapReview, "🔵 SIAP REVIEW")]
    [InlineData("DRAFTED", false, false, DashboardStatus.SiapReview, "🔵 SIAP REVIEW")]
    [InlineData("PERLU_REVIEW", false, false, DashboardStatus.SiapReview, "🔵 SIAP REVIEW")]
    [InlineData("PERLU_INPUT", false, false, DashboardStatus.PerluInput, "🟡 PERLU_INPUT")]
    [InlineData("LIBUR", false, true, DashboardStatus.Libur, "⚪ LIBUR")]
    [InlineData("PERLU_TINDAKAN", false, false, DashboardStatus.PerluTindakan, "🔴 PERLU_TINDAKAN")]
    [InlineData("ERROR", false, false, DashboardStatus.PerluTindakan, "🔴 PERLU_TINDAKAN")]
    public void TestMapStatusStringToEnumAndText(
        string statusStr,
        bool hasSubmitted,
        bool isHoliday,
        DashboardStatus expectedStatus,
        string expectedTextPrefix)
    {
        var status = DashboardStatusHelper.MapStatus(statusStr, hasSubmitted, isHoliday);
        Assert.Equal(expectedStatus, status);

        var text = DashboardStatusHelper.GetBadgeText(status);
        Assert.StartsWith(expectedTextPrefix, text);
    }

    [Fact]
    public void TestStatusColorMapping()
    {
        Assert.Equal(Color.FromArgb(200, 230, 200), DashboardStatusHelper.GetBadgeColor(DashboardStatus.Berhasil));
        Assert.Equal(Color.FromArgb(200, 210, 240), DashboardStatusHelper.GetBadgeColor(DashboardStatus.SiapReview));
        Assert.Equal(Color.FromArgb(255, 245, 200), DashboardStatusHelper.GetBadgeColor(DashboardStatus.PerluInput));
        Assert.Equal(Color.FromArgb(230, 230, 230), DashboardStatusHelper.GetBadgeColor(DashboardStatus.Libur));
        Assert.Equal(Color.FromArgb(255, 210, 210), DashboardStatusHelper.GetBadgeColor(DashboardStatus.PerluTindakan));
        Assert.Equal(Color.FromArgb(255, 210, 210), DashboardStatusHelper.GetBadgeColor(DashboardStatus.Offline));
    }

    [Fact]
    public void TestOfflineBadgeText()
    {
        var text = DashboardStatusHelper.GetBadgeText(DashboardStatus.Offline);
        Assert.Equal("⚠️ Backend tidak terhubung", text);
    }

    [Fact]
    public void TestHolidayWithCustomName()
    {
        var text = DashboardStatusHelper.GetBadgeText(DashboardStatus.Libur, "Hari Raya Idul Fitri");
        Assert.Equal("⚪ LIBUR (Hari Raya Idul Fitri)", text);
    }
}
