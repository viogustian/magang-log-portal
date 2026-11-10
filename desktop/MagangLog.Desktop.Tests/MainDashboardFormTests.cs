using MagangLog.Desktop.Forms;
using MagangLog.Desktop.Services;
using Xunit;

namespace MagangLog.Desktop.Tests;

public class MainDashboardFormTests
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
    public void TestIsOnboardingRequiredWhenConfigMissing()
    {
        RunSta(() =>
        {
            var handler = new MockHttpMessageHandler("{}");
            var client = new BackendApiClient(new HttpClient(handler));

            using var form = new MainDashboardForm(client)
            {
                ConfigFilePath = "non_existent_config_file_path.yaml",
                OnboardingComplete = false
            };

            Assert.True(form.IsOnboardingRequired());
        });
    }

    [Fact]
    public void TestIsOnboardingRequiredWhenConfigExists()
    {
        RunSta(() =>
        {
            var tempConfig = Path.GetTempFileName();
            try
            {
                File.WriteAllText(tempConfig, "timezone: Asia/Jakarta");

                var handler = new MockHttpMessageHandler("{}");
                var client = new BackendApiClient(new HttpClient(handler));

                using var form = new MainDashboardForm(client)
                {
                    ConfigFilePath = tempConfig,
                    OnboardingComplete = false
                };

                Assert.False(form.IsOnboardingRequired());
            }
            finally
            {
                if (File.Exists(tempConfig))
                {
                    File.Delete(tempConfig);
                }
            }
        });
    }

    [Fact]
    public void TestIsOnboardingRequiredWhenOnboardingAlreadyComplete()
    {
        RunSta(() =>
        {
            var handler = new MockHttpMessageHandler("{}");
            var client = new BackendApiClient(new HttpClient(handler));

            using var form = new MainDashboardForm(client)
            {
                ConfigFilePath = "non_existent_config_file_path.yaml",
                OnboardingComplete = true
            };

            Assert.False(form.IsOnboardingRequired());
        });
    }

    [Fact]
    public void TestMainDashboardFormLayoutAndDefaultSizes()
    {
        RunSta(() =>
        {
            var handler = new MockHttpMessageHandler("{}");
            var client = new BackendApiClient(new HttpClient(handler));

            using var form = new MainDashboardForm(client);

            Assert.Equal(new Size(1024, 720), form.Size);
            Assert.Equal(new Size(800, 600), form.MinimumSize);
            Assert.NotNull(form.StatusBanner);
            Assert.NotNull(form.MainSplitContainer);
            Assert.NotNull(form.CalendarPanel);
        });
    }

    [Fact]
    public void TestPollingTimerIntervalIsSixtySeconds()
    {
        RunSta(() =>
        {
            var handler = new MockHttpMessageHandler("{}");
            var client = new BackendApiClient(new HttpClient(handler));

            using var form = new MainDashboardForm(client);

            Assert.NotNull(form.PollingTimer);
            Assert.Equal(60000, form.PollingTimer.Interval);
        });
    }

    [Fact]
    public async Task TestRefreshStatusAsync_Success()
    {
        var cannedJson = """
        {
            "target_date": "2026-11-10",
            "status": "SIAP REVIEW",
            "is_workday": true,
            "is_holiday": false,
            "holiday_name": null,
            "has_submitted_entry": false,
            "needs_user_action": true
        }
        """;

        var handler = new MockHttpMessageHandler(cannedJson);
        var client = new BackendApiClient(new HttpClient(handler));

        MainDashboardForm? form = null;
        RunSta(() =>
        {
            form = new MainDashboardForm(client);
        });

        try
        {
            await form!.RefreshStatusAsync();

            Assert.Equal(Models.DashboardStatus.SiapReview, form.StatusBanner.CurrentStatus);
            Assert.Equal("🔵 SIAP REVIEW", form.StatusBanner.StatusBadgeLabel.Text);
            Assert.False(form.StatusBanner.IsOffline);
        }
        finally
        {
            form?.Dispose();
        }
    }

    [Fact]
    public async Task TestRefreshStatusAsync_OfflineResilience()
    {
        var handler = new MockHttpMessageHandler(_ => throw new HttpRequestException("Backend unreachable"));
        var client = new BackendApiClient(new HttpClient(handler));

        MainDashboardForm? form = null;
        RunSta(() =>
        {
            form = new MainDashboardForm(client);
        });

        try
        {
            await form!.RefreshStatusAsync();

            Assert.Equal(Models.DashboardStatus.Offline, form.StatusBanner.CurrentStatus);
            Assert.True(form.StatusBanner.IsOffline);
            Assert.Equal("⚠️ Backend tidak terhubung", form.StatusBanner.StatusBadgeLabel.Text);
            Assert.False(form.StatusBanner.RunPipelineButton.Enabled);
        }
        finally
        {
            form?.Dispose();
        }
    }

    [Fact]
    public void TestOpenPortalActionTriggersConfiguredUrl()
    {
        RunSta(() =>
        {
            var handler = new MockHttpMessageHandler("{}");
            var client = new BackendApiClient(new HttpClient(handler));

            using var form = new MainDashboardForm(client);

            string? openedUrl = null;
            form.UrlOpener = url => openedUrl = url;

            form.OpenPortal();

            Assert.Equal("https://monev.maganghub.kemnaker.go.id/dashboard/riwayat", openedUrl);
        });
    }

    [Fact]
    public async Task TestRunPipelineActionTriggersApiAndRefreshesStatus()
    {
        var draftJson = """
        {
            "success": true,
            "work_date": "2026-11-10"
        }
        """;
        var statusJson = """
        {
            "target_date": "2026-11-10",
            "status": "SIAP REVIEW",
            "is_workday": true,
            "is_holiday": false,
            "holiday_name": null,
            "has_submitted_entry": false,
            "needs_user_action": true
        }
        """;

        var handler = new MockHttpMessageHandler(req =>
        {
            if (req.Method == HttpMethod.Post && req.RequestUri!.AbsolutePath.Contains("/api/entry/draft"))
            {
                return new HttpResponseMessage(System.Net.HttpStatusCode.OK)
                {
                    Content = new StringContent(draftJson, System.Text.Encoding.UTF8, "application/json")
                };
            }
            if (req.Method == HttpMethod.Get && req.RequestUri!.AbsolutePath.Contains("/api/status/today"))
            {
                return new HttpResponseMessage(System.Net.HttpStatusCode.OK)
                {
                    Content = new StringContent(statusJson, System.Text.Encoding.UTF8, "application/json")
                };
            }
            return new HttpResponseMessage(System.Net.HttpStatusCode.NotFound);
        });

        var client = new BackendApiClient(new HttpClient(handler));

        MainDashboardForm? form = null;
        RunSta(() =>
        {
            form = new MainDashboardForm(client);
        });

        try
        {
            await form!.RunPipelineManualAsync();

            Assert.Equal(Models.DashboardStatus.SiapReview, form.StatusBanner.CurrentStatus);
            Assert.Equal("🔵 SIAP REVIEW", form.StatusBanner.StatusBadgeLabel.Text);
        }
        finally
        {
            form?.Dispose();
        }
    }
}

