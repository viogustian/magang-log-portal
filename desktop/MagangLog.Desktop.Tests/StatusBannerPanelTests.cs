using System.Drawing;
using System.Globalization;
using MagangLog.Desktop.Controls;
using MagangLog.Desktop.Models;
using Xunit;

namespace MagangLog.Desktop.Tests;

public class StatusBannerPanelTests
{
    private static void RunSta(Action action)
    {
        Exception? ex = null;
        var thread = new Thread(() =>
        {
            try
            {
                action();
            }
            catch (Exception e)
            {
                ex = e;
            }
        });
        thread.SetApartmentState(ApartmentState.STA);
        thread.Start();
        thread.Join();

        if (ex != null)
        {
            System.Runtime.ExceptionServices.ExceptionDispatchInfo.Capture(ex).Throw();
        }
    }

    [Fact]
    public void TestStatusBannerPanelInitializesWithIndonesianDate()
    {
        RunSta(() =>
        {
            using var panel = new StatusBannerPanel();

            Assert.Equal(DockStyle.Top, panel.Dock);
            Assert.True(panel.Height >= 70 && panel.Height <= 100);
            Assert.NotNull(panel.DateLabel);
            Assert.NotEmpty(panel.DateLabel.Text);

            // Indonesian day/month name check
            var idCulture = new CultureInfo("id-ID");
            var expectedDayName = DateTime.Now.ToString("dddd", idCulture);
            Assert.Contains(expectedDayName, panel.DateLabel.Text, StringComparison.OrdinalIgnoreCase);
        });
    }

    [Fact]
    public void TestStatusBannerPanelUpdatesToSuccessStatus()
    {
        RunSta(() =>
        {
            using var panel = new StatusBannerPanel();
            var response = new TodayStatusResponse
            {
                TargetDate = "2026-11-10",
                Status = "BERHASIL",
                HasSubmittedEntry = true
            };

            panel.UpdateStatus(response);

            Assert.Equal(DashboardStatus.Berhasil, panel.CurrentStatus);
            Assert.Equal("🟢 BERHASIL", panel.StatusBadgeLabel.Text);
            Assert.Equal(Color.FromArgb(200, 230, 200), panel.StatusBadgeLabel.BackColor);
            Assert.True(panel.RunPipelineButton.Enabled);
            Assert.True(panel.OpenPortalButton.Enabled);
        });
    }

    [Fact]
    public void TestStatusBannerPanelUpdatesToSiapReviewStatus()
    {
        RunSta(() =>
        {
            using var panel = new StatusBannerPanel();
            var response = new TodayStatusResponse
            {
                TargetDate = "2026-11-10",
                Status = "DRAFTED",
                NeedsUserAction = true
            };

            panel.UpdateStatus(response);

            Assert.Equal(DashboardStatus.SiapReview, panel.CurrentStatus);
            Assert.Equal("🔵 SIAP REVIEW", panel.StatusBadgeLabel.Text);
            Assert.Equal(Color.FromArgb(200, 210, 240), panel.StatusBadgeLabel.BackColor);
        });
    }

    [Fact]
    public void TestStatusBannerPanelUpdatesToPerluInputStatus()
    {
        RunSta(() =>
        {
            using var panel = new StatusBannerPanel();
            var response = new TodayStatusResponse
            {
                TargetDate = "2026-11-10",
                Status = "PERLU_INPUT",
                NeedsUserAction = true
            };

            panel.UpdateStatus(response);

            Assert.Equal(DashboardStatus.PerluInput, panel.CurrentStatus);
            Assert.Equal("🟡 PERLU_INPUT", panel.StatusBadgeLabel.Text);
            Assert.Equal(Color.FromArgb(255, 245, 200), panel.StatusBadgeLabel.BackColor);
        });
    }

    [Fact]
    public void TestStatusBannerPanelUpdatesToHolidayStatus()
    {
        RunSta(() =>
        {
            using var panel = new StatusBannerPanel();
            var response = new TodayStatusResponse
            {
                TargetDate = "2026-11-10",
                Status = "LIBUR",
                IsHoliday = true,
                HolidayName = "Tahun Baru"
            };

            panel.UpdateStatus(response);

            Assert.Equal(DashboardStatus.Libur, panel.CurrentStatus);
            Assert.Equal("⚪ LIBUR (Tahun Baru)", panel.StatusBadgeLabel.Text);
            Assert.Equal(Color.FromArgb(230, 230, 230), panel.StatusBadgeLabel.BackColor);
        });
    }

    [Fact]
    public void TestStatusBannerPanelUpdatesToOfflineStatusDisablesActionButtons()
    {
        RunSta(() =>
        {
            using var panel = new StatusBannerPanel();

            panel.UpdateOffline();

            Assert.Equal(DashboardStatus.Offline, panel.CurrentStatus);
            Assert.True(panel.IsOffline);
            Assert.Equal("⚠️ Backend tidak terhubung", panel.StatusBadgeLabel.Text);
            Assert.Equal(Color.FromArgb(255, 210, 210), panel.StatusBadgeLabel.BackColor);
            Assert.False(panel.RunPipelineButton.Enabled);
        });
    }
}
