using MagangLog.Desktop.Forms;
using Xunit;

namespace MagangLog.Desktop.Tests;

public class AboutFormTests
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
    public void TestAboutForm_ContainsDeveloperAndAppMetadata()
    {
        RunSta(() =>
        {
            using var form = new AboutForm();

            Assert.Equal("Tentang Pengembang & Arsitektur Sistem", form.Text);
            Assert.Contains("MagangLog Portal", form.AppTitleLabel.Text);
            Assert.Contains("v2.0.0", form.VersionLabel.Text);

            Assert.Contains("VIO GUSTIAN NUR ALAMSYAH", form.DeveloperNameLabel.Text);
            Assert.Contains("Lead Developer & Creator", form.DeveloperRoleLabel.Text);
            Assert.Contains("@viogustian", form.DeveloperGitHubLabel.Text);

            // Architecture details
            Assert.Contains(".NET 8", form.ArchitectureSpecsText);
            Assert.Contains("FastAPI", form.ArchitectureSpecsText);
            Assert.Contains("Gemini", form.ArchitectureSpecsText);
            Assert.Contains("Playwright", form.ArchitectureSpecsText);
            Assert.Contains("SQLite", form.ArchitectureSpecsText);
        });
    }

    [Fact]
    public void TestAboutForm_OpenGitHub_InvokesUrlOpener()
    {
        RunSta(() =>
        {
            using var form = new AboutForm();
            string? openedUrl = null;
            form.UrlOpener = url => openedUrl = url;

            form.OpenGitHubProfile();

            Assert.Equal("https://github.com/viogustian", openedUrl);
        });
    }

    [Fact]
    public void TestAboutForm_OpenRepository_InvokesUrlOpener()
    {
        RunSta(() =>
        {
            using var form = new AboutForm();
            string? openedUrl = null;
            form.UrlOpener = url => openedUrl = url;

            form.OpenRepository();

            Assert.Equal("https://github.com/viogustian/magang-log-portal", openedUrl);
        });
    }

    [Fact]
    public void TestAboutForm_CloseDialog_ClosesForm()
    {
        RunSta(() =>
        {
            using var form = new AboutForm();
            _ = form.Handle;
            var closed = false;
            form.FormClosed += (s, e) => closed = true;

            form.CloseDialog();

            Assert.True(closed);
        });
    }
}
