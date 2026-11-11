using MagangLog.Desktop.Forms;
using MagangLog.Desktop.Models;
using MagangLog.Desktop.Services;
using Xunit;

namespace MagangLog.Desktop.Tests;

public class AppIconHelperTests
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
    public void TestAppIconHelper_LoadsEmbeddedIconAndBitmap()
    {
        var icon = AppIconHelper.GetAppIcon();
        Assert.NotNull(icon);
        Assert.True(icon.Width > 0 && icon.Height > 0);

        using var bmp32 = AppIconHelper.GetAppBitmap(32);
        using var bmp48 = AppIconHelper.GetAppBitmap(48);
        Assert.NotNull(bmp32);
        Assert.NotNull(bmp48);
        Assert.Equal(32, bmp32.Width);
        Assert.Equal(48, bmp48.Width);
    }

    [Fact]
    public void TestAllForms_HaveEmbeddedApplicationIconApplied()
    {
        RunSta(() =>
        {
            var expectedIcon = AppIconHelper.GetAppIcon();
            Assert.NotNull(expectedIcon);

            var client = new BackendApiClient(new HttpClient(new MockHttpMessageHandler("{}")));

            using var dashboard = new MainDashboardForm(client);
            using var wizard = new SetupWizardDialog(client);
            using var settings = new SettingsForm(client);
            using var about = new AboutForm();
            using var dayDetail = new DayDetailForm("2026-11-11", new EntryDetailResponse(), client);

            Assert.Same(expectedIcon, dashboard.Icon);
            Assert.Same(expectedIcon, wizard.Icon);
            Assert.Same(expectedIcon, settings.Icon);
            Assert.Same(expectedIcon, about.Icon);
            Assert.Same(expectedIcon, dayDetail.Icon);
            Assert.True(settings.ShowIcon);

            // Verify header PictureBox logos exist on MainDashboardForm and AboutForm
            var dashboardLogo = dashboard.Controls.OfType<Panel>()
                .SelectMany(p => p.Controls.OfType<PictureBox>())
                .FirstOrDefault();
            Assert.NotNull(dashboardLogo);
            Assert.NotNull(dashboardLogo.Image);

            var aboutLogo = about.Controls.OfType<Panel>()
                .SelectMany(p => p.Controls.OfType<Panel>())
                .SelectMany(p => p.Controls.OfType<PictureBox>())
                .FirstOrDefault();
            Assert.NotNull(aboutLogo);
            Assert.NotNull(aboutLogo.Image);
        });
    }
}

