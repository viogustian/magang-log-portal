#pragma warning disable xUnit1031

using System.Net;
using System.Threading;
using MagangLog.Desktop.Controls;
using MagangLog.Desktop.Services;
using Xunit;

namespace MagangLog.Desktop.Tests;

public class SubmissionModePanelTests
{
    private static async Task RunStaAsync(Func<Task> action)
    {
        var tcs = new TaskCompletionSource();
        var thread = new Thread(() =>
        {
            try
            {
                action().GetAwaiter().GetResult();
                tcs.SetResult();
            }
            catch (Exception ex)
            {
                tcs.SetException(ex);
            }
        });
        thread.SetApartmentState(ApartmentState.STA);
        thread.Start();
        await tcs.Task;
    }

    [Fact]
    public async Task SubmissionMode_DefaultIsReviewAndGateSatisfied()
    {
        await RunStaAsync(() =>
        {
            var panel = new SubmissionModePanel();

            Assert.Equal("review", panel.ReviewMode);
            Assert.True(panel.IsGateSatisfied);
            Assert.False(panel.IsFullAccessWarningVisible);

            panel.Dispose();
            return Task.CompletedTask;
        });
    }

    [Fact]
    public async Task SubmissionMode_FullAccess_RequiresConfirmation()
    {
        await RunStaAsync(() =>
        {
            var panel = new SubmissionModePanel();
            panel.SetMode("auto");

            Assert.Equal("auto", panel.ReviewMode);
            Assert.True(panel.IsFullAccessWarningVisible);
            Assert.False(panel.IsGateSatisfied);

            // Check confirmation box
            panel.FullAccessConfirmed = true;
            Assert.True(panel.IsGateSatisfied);

            // Uncheck confirmation box
            panel.FullAccessConfirmed = false;
            Assert.False(panel.IsGateSatisfied);

            panel.Dispose();
            return Task.CompletedTask;
        });
    }

    [Fact]
    public async Task SubmissionMode_Notify_DoesNotRequireConfirmation()
    {
        await RunStaAsync(() =>
        {
            var panel = new SubmissionModePanel();
            panel.SetMode("notify");

            Assert.Equal("notify", panel.ReviewMode);
            Assert.False(panel.IsFullAccessWarningVisible);
            Assert.True(panel.IsGateSatisfied);

            panel.Dispose();
            return Task.CompletedTask;
        });
    }

    [Fact]
    public async Task SubmissionMode_SetModeWithConfirmedFlag_RestoresState()
    {
        await RunStaAsync(() =>
        {
            var panel = new SubmissionModePanel();
            panel.SetMode("auto", confirmed: true);

            Assert.Equal("auto", panel.ReviewMode);
            Assert.True(panel.FullAccessConfirmed);
            Assert.True(panel.IsGateSatisfied);

            panel.Dispose();
            return Task.CompletedTask;
        });
    }

    [Fact]
    public async Task SubmissionMode_RadioButtons_MutualExclusion_NoDoubleSelection()
    {
        await RunStaAsync(() =>
        {
            var panel = new SubmissionModePanel();

            // Initially Review is checked
            Assert.True(panel.RadioReview.Checked);
            Assert.False(panel.RadioAuto.Checked);
            Assert.False(panel.RadioNotify.Checked);

            // User clicks Auto
            panel.RadioAuto.Checked = true;
            Assert.False(panel.RadioReview.Checked);
            Assert.True(panel.RadioAuto.Checked);
            Assert.False(panel.RadioNotify.Checked);

            // User clicks Notify twice
            panel.RadioNotify.Checked = true;
            panel.RadioNotify.Checked = true;
            Assert.False(panel.RadioReview.Checked);
            Assert.False(panel.RadioAuto.Checked);
            Assert.True(panel.RadioNotify.Checked);

            // User clicks back to Review twice
            panel.RadioReview.Checked = true;
            panel.RadioReview.Checked = true;
            Assert.True(panel.RadioReview.Checked);
            Assert.False(panel.RadioAuto.Checked);
            Assert.False(panel.RadioNotify.Checked);

            panel.Dispose();
            return Task.CompletedTask;
        });
    }

    [Fact]
    public async Task SubmissionMode_RefreshAuthStatus_Authenticated_UpdatesLabelAndState()
    {
        await RunStaAsync(async () =>
        {
            var handler = new MockHttpMessageHandler(req =>
            {
                if (req.RequestUri!.AbsolutePath.Contains("/auth-status"))
                {
                    return new HttpResponseMessage(HttpStatusCode.OK)
                    {
                        Content = new StringContent("""
                        {
                            "authenticated": true,
                            "username": "vio.gustian",
                            "session_status": "valid"
                        }
                        """, System.Text.Encoding.UTF8, "application/json")
                    };
                }
                return new HttpResponseMessage(HttpStatusCode.NotFound);
            });

            var client = new BackendApiClient(new HttpClient(handler));
            using var panel = new SubmissionModePanel(client);

            await panel.RefreshAuthStatusAsync();

            Assert.True(panel.IsPortalAuthenticated);
            Assert.Contains("Sesi Aktif", panel.PortalStatusLabel.Text);
            Assert.Contains("vio.gustian", panel.PortalStatusLabel.Text);
        });
    }

    [Fact]
    public async Task SubmissionMode_RefreshAuthStatus_Unauthenticated_UpdatesLabelAndState()
    {
        await RunStaAsync(async () =>
        {
            var handler = new MockHttpMessageHandler(req =>
            {
                if (req.RequestUri!.AbsolutePath.Contains("/auth-status"))
                {
                    return new HttpResponseMessage(HttpStatusCode.OK)
                    {
                        Content = new StringContent("""
                        {
                            "authenticated": false,
                            "session_status": "missing"
                        }
                        """, System.Text.Encoding.UTF8, "application/json")
                    };
                }
                return new HttpResponseMessage(HttpStatusCode.NotFound);
            });

            var client = new BackendApiClient(new HttpClient(handler));
            using var panel = new SubmissionModePanel(client);

            await panel.RefreshAuthStatusAsync();

            Assert.False(panel.IsPortalAuthenticated);
            Assert.Contains("Belum Ada / Kedaluwarsa", panel.PortalStatusLabel.Text);
        });
    }

    [Fact]
    public async Task SubmissionMode_OpenPortalLogin_Success_UpdatesAndRefreshes()
    {
        await RunStaAsync(async () =>
        {
            var isAuth = false;
            var handler = new MockHttpMessageHandler(req =>
            {
                if (req.RequestUri!.AbsolutePath.Contains("/open-login"))
                {
                    isAuth = true;
                    return new HttpResponseMessage(HttpStatusCode.OK)
                    {
                        Content = new StringContent("""
                        {
                            "success": true,
                            "authenticated": true,
                            "message": "Login berhasil disimpan."
                        }
                        """, System.Text.Encoding.UTF8, "application/json")
                    };
                }
                if (req.RequestUri!.AbsolutePath.Contains("/auth-status"))
                {
                    return new HttpResponseMessage(HttpStatusCode.OK)
                    {
                        Content = new StringContent($$"""
                        {
                            "authenticated": {{(isAuth ? "true" : "false")}},
                            "username": "vio.gustian",
                            "session_status": "valid"
                        }
                        """, System.Text.Encoding.UTF8, "application/json")
                    };
                }
                return new HttpResponseMessage(HttpStatusCode.NotFound);
            });

            var client = new BackendApiClient(new HttpClient(handler));
            using var panel = new SubmissionModePanel(client);

            await panel.OpenPortalLoginAsync();

            Assert.True(panel.IsPortalAuthenticated);
            Assert.Contains("Sesi Aktif", panel.PortalStatusLabel.Text);
        });
    }
}

