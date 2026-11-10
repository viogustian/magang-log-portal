using MagangLog.Desktop.Forms;
using MagangLog.Desktop.Models;
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
            Assert.NotNull(form.EvidencePanel);
            Assert.NotNull(form.DraftEditor);
            Assert.Contains(form.DraftEditor, form.MainSplitContainer.Panel1.Controls.Cast<Control>());
            Assert.Contains(form.EvidencePanel, form.MainSplitContainer.Panel2.Controls.Cast<Control>());
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
    public async Task TestRefreshStatusAsyncUpdatesEvidenceFeed()
    {
        var statusJson = """
        {
            "target_date": "2026-11-10",
            "status": "SIAP REVIEW",
            "is_workday": true,
            "is_holiday": false,
            "has_submitted_entry": false,
            "needs_user_action": true
        }
        """;
        var evidenceJson = """
        {
            "items": [
                {
                    "id": "ev-10",
                    "source": "git",
                    "kind": "commit",
                    "ts": "2026-11-10T11:00:00Z",
                    "title": "feat: timeline grid",
                    "detail": "sample detail",
                    "strength": "strong"
                }
            ]
        }
        """;

        var handler = new MockHttpMessageHandler(req =>
        {
            if (req.RequestUri!.AbsolutePath.Contains("/api/status/today"))
            {
                return new HttpResponseMessage(System.Net.HttpStatusCode.OK)
                {
                    Content = new StringContent(statusJson, System.Text.Encoding.UTF8, "application/json")
                };
            }
            if (req.RequestUri!.AbsolutePath.Contains("/api/evidence/today"))
            {
                return new HttpResponseMessage(System.Net.HttpStatusCode.OK)
                {
                    Content = new StringContent(evidenceJson, System.Text.Encoding.UTF8, "application/json")
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
            await form!.RefreshStatusAsync();

            Assert.Single(form.EvidencePanel.AllItems);
            Assert.Equal("feat: timeline grid", form.EvidencePanel.AllItems[0].Title);
            Assert.Single(form.EvidencePanel.EvidenceGrid.Rows);
        }
        finally
        {
            form?.Dispose();
        }
    }

    [Fact]
    public async Task TestRefreshStatusAsyncUpdatesDraftEditor()
    {
        var statusJson = """
        {
            "target_date": "2026-11-10",
            "status": "SIAP REVIEW",
            "is_workday": true,
            "is_holiday": false,
            "has_submitted_entry": false,
            "needs_user_action": true
        }
        """;
        var entryJson = """
        {
            "entry_id": "entry-today",
            "work_date": "2026-11-10",
            "kehadiran": "Hadir",
            "aktivitas": "Melakukan implementasi komponen UI draf reviewer dan character counting.",
            "pembelajaran": "Memahami pola MVVM dan WinForms layout flow panel.",
            "kendala": "Integrasi asynchronous event perlu penanganan STA thread cermat.",
            "status": "DRAFTED",
            "validation_passed": true,
            "validation_errors": []
        }
        """;

        var handler = new MockHttpMessageHandler(req =>
        {
            if (req.RequestUri!.AbsolutePath.Contains("/api/status/today"))
            {
                return new HttpResponseMessage(System.Net.HttpStatusCode.OK)
                {
                    Content = new StringContent(statusJson, System.Text.Encoding.UTF8, "application/json")
                };
            }
            if (req.RequestUri!.AbsolutePath.Contains("/api/entry/today"))
            {
                return new HttpResponseMessage(System.Net.HttpStatusCode.OK)
                {
                    Content = new StringContent(entryJson, System.Text.Encoding.UTF8, "application/json")
                };
            }
            return new HttpResponseMessage(System.Net.HttpStatusCode.OK)
            {
                Content = new StringContent("{\"items\":[]}", System.Text.Encoding.UTF8, "application/json")
            };
        });

        var client = new BackendApiClient(new HttpClient(handler));

        MainDashboardForm? form = null;
        RunSta(() =>
        {
            form = new MainDashboardForm(client);
        });

        try
        {
            await form!.RefreshStatusAsync();

            Assert.Equal("Melakukan implementasi komponen UI draf reviewer dan character counting.", form.DraftEditor.AktivitasTextBox.Text);
            Assert.Equal("Memahami pola MVVM dan WinForms layout flow panel.", form.DraftEditor.PembelajaranTextBox.Text);
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

    [Fact]
    public async Task TestRefreshStatusAsync_SwitchesToFallbackNoteModeWhenPerluInput()
    {
        var statusJson = """
        {
            "target_date": "2026-11-10",
            "status": "PERLU_INPUT",
            "is_workday": true,
            "is_holiday": false,
            "holiday_name": null,
            "has_submitted_entry": false,
            "needs_user_action": true
        }
        """;

        var handler = new MockHttpMessageHandler(req =>
        {
            if (req.RequestUri!.AbsolutePath.Contains("/api/status/today"))
            {
                return new HttpResponseMessage(System.Net.HttpStatusCode.OK)
                {
                    Content = new StringContent(statusJson, System.Text.Encoding.UTF8, "application/json")
                };
            }
            if (req.RequestUri!.AbsolutePath.Contains("/api/evidence/today"))
            {
                return new HttpResponseMessage(System.Net.HttpStatusCode.OK)
                {
                    Content = new StringContent("{\"items\":[]}", System.Text.Encoding.UTF8, "application/json")
                };
            }
            if (req.RequestUri!.AbsolutePath.Contains("/api/entry/today"))
            {
                return new HttpResponseMessage(System.Net.HttpStatusCode.OK)
                {
                    Content = new StringContent("{}", System.Text.Encoding.UTF8, "application/json")
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
            await form!.RefreshStatusAsync();

            Assert.Equal(DashboardMode.FallbackNote, form.CurrentMode);
            Assert.True(form.IsFallbackNoteVisible);
            Assert.False(form.IsDraftEditorVisible);
        }
        finally
        {
            form?.Dispose();
        }
    }

    [Fact]
    public void TestSetDashboardMode_TogglesVisibilityDirectly()
    {
        RunSta(() =>
        {
            var handler = new MockHttpMessageHandler("{}");
            var client = new BackendApiClient(new HttpClient(handler));
            using var form = new MainDashboardForm(client);

            form.SetDashboardMode(DashboardMode.FallbackNote);
            Assert.Equal(DashboardMode.FallbackNote, form.CurrentMode);
            Assert.True(form.IsFallbackNoteVisible);
            Assert.False(form.IsDraftEditorVisible);

            form.SetDashboardMode(DashboardMode.DraftEditor);
            Assert.Equal(DashboardMode.DraftEditor, form.CurrentMode);
            Assert.False(form.IsFallbackNoteVisible);
            Assert.True(form.IsDraftEditorVisible);
        });
    }

    [Fact]
    public void TestFallbackNote_SwitchToEditorRequested_RestoresDraftEditorMode()
    {
        RunSta(() =>
        {
            var handler = new MockHttpMessageHandler("{}");
            var client = new BackendApiClient(new HttpClient(handler));
            using var form = new MainDashboardForm(client);

            form.SetDashboardMode(DashboardMode.FallbackNote);
            Assert.Equal(DashboardMode.FallbackNote, form.CurrentMode);
            Assert.True(form.IsFallbackNoteVisible);

            form.FallbackNote.SwitchToEditor();
            Assert.Equal(DashboardMode.DraftEditor, form.CurrentMode);
            Assert.False(form.IsFallbackNoteVisible);
            Assert.True(form.IsDraftEditorVisible);
        });
    }
}

