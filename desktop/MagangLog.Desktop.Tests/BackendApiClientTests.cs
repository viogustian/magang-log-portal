using System.Net;
using System.Text.Json;
using MagangLog.Desktop.Models;
using MagangLog.Desktop.Services;
using Xunit;

namespace MagangLog.Desktop.Tests;

public class BackendApiClientTests
{
    [Fact]
    public async Task TestGetWizardProgressAsync()
    {
        var cannedJson = """
        {
            "current_step": 3,
            "completed_steps": [0, 1, 2],
            "step_data": {
                "git_intensity": "sering"
            }
        }
        """;

        var handler = new MockHttpMessageHandler(cannedJson);
        var httpClient = new HttpClient(handler);
        var client = new BackendApiClient(httpClient);

        var state = await client.GetWizardProgressAsync();

        Assert.Equal(3, state.CurrentStep);
        Assert.Equal(new List<int> { 0, 1, 2 }, state.CompletedSteps);
        Assert.Single(handler.SentRequests);
        Assert.Equal(HttpMethod.Get, handler.SentRequests[0].Method);
        Assert.EndsWith("/api/setup/wizard-progress", handler.SentRequests[0].RequestUri!.AbsolutePath);
    }

    [Fact]
    public async Task TestSaveWizardProgressAsync()
    {
        var cannedJson = """
        {
            "success": true,
            "saved_at": "2026-11-09T22:00:00Z"
        }
        """;

        var handler = new MockHttpMessageHandler(cannedJson);
        var httpClient = new HttpClient(handler);
        var client = new BackendApiClient(httpClient);

        var state = new WizardProgressState
        {
            CurrentStep = 1,
            CompletedSteps = new List<int> { 0 },
            StepData = new Dictionary<string, object?> { ["folder"] = "C:/Projects" }
        };

        var response = await client.SaveWizardProgressAsync(state);

        Assert.True(response.Success);
        Assert.Equal("2026-11-09T22:00:00Z", response.SavedAt);
        Assert.Single(handler.SentRequests);
        Assert.Equal(HttpMethod.Post, handler.SentRequests[0].Method);
        Assert.EndsWith("/api/setup/save-progress", handler.SentRequests[0].RequestUri!.AbsolutePath);

        var sentContent = await handler.SentRequests[0].Content!.ReadAsStringAsync();
        var sentState = JsonSerializer.Deserialize<WizardProgressState>(sentContent);
        Assert.NotNull(sentState);
        Assert.Equal(1, sentState.CurrentStep);
    }

    [Fact]
    public async Task TestPredictProfileAsync_ReturnsPredictedProfile()
    {
        var cannedJson = """
        {
            "source": "gemini",
            "profile": {
                "profile_name": "Software Engineer",
                "natural_description": "Coding and testing",
                "applications": [
                    {
                        "name": "Visual Studio Code",
                        "process_names": ["Code.exe"],
                        "file_extensions": [".cs"],
                        "log_patterns": []
                    }
                ],
                "browser_domains": ["github.com"],
                "watch_folders": []
            }
        }
        """;

        var handler = new MockHttpMessageHandler(cannedJson);
        var httpClient = new HttpClient(handler);
        var client = new BackendApiClient(httpClient);

        var result = await client.PredictProfileAsync("Saya membuat program C#");

        Assert.NotNull(result);
        Assert.Equal("gemini", result.Source);
        Assert.Equal("Software Engineer", result.Profile.ProfileName);
        var keywords = result.Profile.ExtractKeywords();
        Assert.Contains("Visual Studio Code", keywords);
        Assert.Contains("Code.exe", keywords);
    }

    [Fact]
    public async Task TestGetPresetsAsync_ReturnsListOfPresets()
    {
        var cannedJson = """
        [
            {
                "profile_name": "UI/UX Designer",
                "natural_description": "Desain mockup Figma",
                "applications": [
                    {
                        "name": "Figma",
                        "process_names": ["Figma.exe"],
                        "file_extensions": [".fig"],
                        "log_patterns": []
                    }
                ],
                "browser_domains": ["figma.com"],
                "watch_folders": []
            }
        ]
        """;

        var handler = new MockHttpMessageHandler(cannedJson);
        var httpClient = new HttpClient(handler);
        var client = new BackendApiClient(httpClient);

        var presets = await client.GetPresetsAsync();

        Assert.Single(presets);
        Assert.Equal("UI/UX Designer", presets[0].ProfileName);
        Assert.Contains("Figma.exe", presets[0].ExtractKeywords());
    }

    [Fact]
    public async Task TestSaveConfigAsync_PostsToSaveEndpoint()
    {
        var cannedJson = """
        {
            "success": true,
            "saved_at": "2026-11-09T22:30:00Z"
        }
        """;

        var handler = new MockHttpMessageHandler(cannedJson);
        var httpClient = new HttpClient(handler);
        var client = new BackendApiClient(httpClient);

        var req = new SaveConfigRequest
        {
            Timezone = "Asia/Jakarta",
            Review = new ReviewSettingsDto { Mode = "review" },
            Sources = new SourcesSettingsDto
            {
                Git = new GitSourceSettingsDto { Enabled = true, Repositories = new List<string> { "C:/Repo" } }
            }
        };

        var response = await client.SaveConfigAsync(req);

        Assert.True(response.Success);
        Assert.Equal("2026-11-09T22:30:00Z", response.SavedAt);
        Assert.Single(handler.SentRequests);
        Assert.Equal(HttpMethod.Post, handler.SentRequests[0].Method);
        Assert.EndsWith("/api/setup/save", handler.SentRequests[0].RequestUri!.AbsolutePath);
    }

    [Fact]
    public async Task TestGetTodayStatusAsync_Success()
    {
        var cannedJson = """
        {
            "target_date": "2026-11-10",
            "status": "SIAP_REVIEW",
            "is_workday": true,
            "is_holiday": false,
            "holiday_name": null,
            "has_submitted_entry": false,
            "needs_user_action": true
        }
        """;

        var handler = new MockHttpMessageHandler(cannedJson);
        var client = new BackendApiClient(new HttpClient(handler));

        var result = await client.GetTodayStatusAsync();

        Assert.NotNull(result);
        Assert.Equal("2026-11-10", result.TargetDate);
        Assert.Equal("SIAP_REVIEW", result.Status);
        Assert.True(result.IsWorkday);
        Assert.False(result.IsHoliday);
        Assert.Single(handler.SentRequests);
        Assert.Equal(HttpMethod.Get, handler.SentRequests[0].Method);
        Assert.Contains("/api/status/today", handler.SentRequests[0].RequestUri!.AbsolutePath);
    }

    [Fact]
    public async Task TestGetTodayStatusAsync_OfflineExceptionReturnsNull()
    {
        var handler = new MockHttpMessageHandler(_ => throw new HttpRequestException("Connection refused"));
        var client = new BackendApiClient(new HttpClient(handler));

        var result = await client.GetTodayStatusAsync();

        Assert.Null(result);
    }

    [Fact]
    public async Task TestTriggerPipelineAsync_Success()
    {
        var cannedJson = """
        {
            "success": true,
            "work_date": "2026-11-10"
        }
        """;

        var handler = new MockHttpMessageHandler(cannedJson);
        var client = new BackendApiClient(new HttpClient(handler));

        var result = await client.TriggerPipelineAsync("2026-11-10");

        Assert.True(result);
        Assert.Single(handler.SentRequests);
        Assert.Equal(HttpMethod.Post, handler.SentRequests[0].Method);
        Assert.EndsWith("/api/entry/draft", handler.SentRequests[0].RequestUri!.AbsolutePath);
    }

    [Fact]
    public async Task TestTriggerPipelineAsync_OfflineExceptionReturnsFalse()
    {
        var handler = new MockHttpMessageHandler(_ => throw new HttpRequestException("Connection refused"));
        var client = new BackendApiClient(new HttpClient(handler));

        var result = await client.TriggerPipelineAsync();

        Assert.False(result);
    }

    [Fact]
    public async Task TestGetEvidenceTodayAsync_Success()
    {
        var cannedJson = """
        {
            "items": [
                {
                    "id": "ev-1",
                    "source": "git",
                    "kind": "commit",
                    "ts": "2026-11-10T09:15:00Z",
                    "title": "feat: timeline feed",
                    "detail": "added evidence panel",
                    "strength": "strong"
                }
            ]
        }
        """;

        var handler = new MockHttpMessageHandler(cannedJson);
        var client = new BackendApiClient(new HttpClient(handler));

        var items = await client.GetEvidenceTodayAsync();

        Assert.Single(items);
        Assert.Equal("ev-1", items[0].Id);
        Assert.Equal("git", items[0].Source);
        Assert.Single(handler.SentRequests);
        Assert.Equal(HttpMethod.Get, handler.SentRequests[0].Method);
        Assert.Contains("/api/evidence/today", handler.SentRequests[0].RequestUri!.AbsolutePath);
    }

    [Fact]
    public async Task TestGetEvidenceTodayAsync_OfflineReturnsEmptyList()
    {
        var handler = new MockHttpMessageHandler(_ => throw new HttpRequestException("Backend unreachable"));
        var client = new BackendApiClient(new HttpClient(handler));

        var items = await client.GetEvidenceTodayAsync();

        Assert.NotNull(items);
        Assert.Empty(items);
    }

    [Fact]
    public async Task TestGetTodayEntryAsync_Success()
    {
        var cannedJson = """
        {
            "entry_id": "entry-1",
            "work_date": "2026-11-10",
            "kehadiran": "Hadir",
            "aktivitas": "Membuat fitur editor draf",
            "pembelajaran": "WinForms .NET 8",
            "kendala": "Tidak ada",
            "status": "DRAFTED",
            "validation_passed": true,
            "validation_errors": []
        }
        """;

        var handler = new MockHttpMessageHandler(cannedJson);
        var client = new BackendApiClient(new HttpClient(handler));

        var entry = await client.GetTodayEntryAsync("2026-11-10");

        Assert.NotNull(entry);
        Assert.Equal("entry-1", entry.EntryId);
        Assert.Equal("Hadir", entry.Kehadiran);
        Assert.Single(handler.SentRequests);
        Assert.Equal(HttpMethod.Get, handler.SentRequests[0].Method);
        Assert.Contains("/api/entry/today", handler.SentRequests[0].RequestUri!.AbsolutePath);
    }

    [Fact]
    public async Task TestEditEntryAsync_Success()
    {
        var cannedJson = """
        {
            "success": true,
            "validation_passed": true,
            "validation_errors": []
        }
        """;

        var handler = new MockHttpMessageHandler(cannedJson);
        var client = new BackendApiClient(new HttpClient(handler));

        var req = new EditEntryRequest
        {
            WorkDate = "2026-11-10",
            Kehadiran = "Hadir",
            Aktivitas = new string('A', 150),
            Pembelajaran = new string('B', 150),
            Kendala = new string('C', 150)
        };

        var response = await client.EditEntryAsync(req);

        Assert.NotNull(response);
        Assert.True(response.Success);
        Assert.Single(handler.SentRequests);
        Assert.Equal(HttpMethod.Post, handler.SentRequests[0].Method);
        Assert.EndsWith("/api/entry/edit", handler.SentRequests[0].RequestUri!.AbsolutePath);
    }

    [Fact]
    public async Task TestDraftEntryAsync_Success()
    {
        var cannedJson = """
        {
            "success": true,
            "validation_passed": true,
            "validation_errors": []
        }
        """;

        var handler = new MockHttpMessageHandler(cannedJson);
        var client = new BackendApiClient(new HttpClient(handler));

        var response = await client.DraftEntryAsync("2026-11-10");

        Assert.NotNull(response);
        Assert.True(response.Success);
        Assert.Single(handler.SentRequests);
        Assert.Equal(HttpMethod.Post, handler.SentRequests[0].Method);
        Assert.EndsWith("/api/entry/draft", handler.SentRequests[0].RequestUri!.AbsolutePath);
    }

    [Fact]
    public async Task TestApproveEntryAsync_Success()
    {
        var cannedJson = """
        {
            "success": true,
            "final_status": "SUDAH_TERKIRIM",
            "error_message": null
        }
        """;

        var handler = new MockHttpMessageHandler(cannedJson);
        var client = new BackendApiClient(new HttpClient(handler));

        var response = await client.ApproveEntryAsync("2026-11-10", dryRun: false);

        Assert.NotNull(response);
        Assert.True(response.Success);
        Assert.Equal("SUDAH_TERKIRIM", response.FinalStatus);
        Assert.Single(handler.SentRequests);
        Assert.Equal(HttpMethod.Post, handler.SentRequests[0].Method);
        Assert.EndsWith("/api/entry/approve", handler.SentRequests[0].RequestUri!.AbsolutePath);
    }

    [Fact]
    public async Task TestPostNoteAsync_Success()
    {
        var cannedJson = """
        {
            "success": true,
            "note_id": "note-abc-999",
            "created_at": "2026-11-10T10:05:00Z"
        }
        """;

        var handler = new MockHttpMessageHandler(cannedJson);
        var client = new BackendApiClient(new HttpClient(handler));

        var req = new CreateNoteRequest
        {
            WorkDate = "2026-11-10",
            Category = "aktivitas",
            Note = "Diskusi perancangan FallbackNotePanel."
        };

        var response = await client.PostNoteAsync(req);

        Assert.NotNull(response);
        Assert.True(response.Success);
        Assert.Equal("note-abc-999", response.NoteId);
        Assert.Single(handler.SentRequests);
        Assert.Equal(HttpMethod.Post, handler.SentRequests[0].Method);
        Assert.EndsWith("/api/notes", handler.SentRequests[0].RequestUri!.AbsolutePath);
    }

    [Fact]
    public async Task TestPostNoteAsync_FailureReturnsNull()
    {
        var handler = new MockHttpMessageHandler("Internal Server Error", HttpStatusCode.InternalServerError);
        var client = new BackendApiClient(new HttpClient(handler));

        var req = new CreateNoteRequest
        {
            WorkDate = "2026-11-10",
            Category = "aktivitas",
            Note = "Diskusi perancangan."
        };

        var response = await client.PostNoteAsync(req);

        Assert.Null(response);
        Assert.Single(handler.SentRequests);
    }

    [Fact]
    public async Task TestGetCalendarMonthAsync_Success()
    {
        var cannedJson = """
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

        var handler = new MockHttpMessageHandler(cannedJson);
        var client = new BackendApiClient(new HttpClient(handler));

        var response = await client.GetCalendarMonthAsync(2026, 10);

        Assert.NotNull(response);
        Assert.Equal(2, response.Days.Count);
        Assert.Equal("2026-10-01", response.Days[0].Date);
        Assert.Equal("TERKIRIM", response.Days[0].Status);
        Assert.Single(handler.SentRequests);
        Assert.Equal(HttpMethod.Get, handler.SentRequests[0].Method);
        Assert.EndsWith("/api/calendar/month", handler.SentRequests[0].RequestUri!.AbsolutePath);
        Assert.Contains("year=2026", handler.SentRequests[0].RequestUri!.Query);
        Assert.Contains("month=10", handler.SentRequests[0].RequestUri!.Query);
    }

    [Fact]
    public async Task TestGetCalendarMonthAsync_FailureReturnsNull()
    {
        var handler = new MockHttpMessageHandler("Server error", HttpStatusCode.InternalServerError);
        var client = new BackendApiClient(new HttpClient(handler));

        var response = await client.GetCalendarMonthAsync(2026, 10);

        Assert.Null(response);
        Assert.Single(handler.SentRequests);
    }

    [Fact]
    public async Task TestGetAppConfigAsync_Success()
    {
        var cannedJson = """
        {
            "timezone": "Asia/Jakarta",
            "workdays": ["mon", "tue", "wed", "thu", "fri"],
            "review": {
                "mode": "review",
                "auto_if_confident": false
            },
            "sources": {
                "git": { "enabled": true, "repositories": ["C:/repos/test"] },
                "browser": { "enabled": false, "allow_domains": [] },
                "app": { "enabled": true }
            }
        }
        """;

        var handler = new MockHttpMessageHandler(cannedJson);
        var client = new BackendApiClient(new HttpClient(handler));

        var config = await client.GetAppConfigAsync();

        Assert.NotNull(config);
        Assert.Equal("Asia/Jakarta", config.Timezone);
        Assert.Equal(5, config.Workdays.Count);
        Assert.True(config.Sources.Git.Enabled);
        Assert.Single(config.Sources.Git.Repositories);
        Assert.Single(handler.SentRequests);
        Assert.Equal(HttpMethod.Get, handler.SentRequests[0].Method);
        Assert.EndsWith("/api/setup/config", handler.SentRequests[0].RequestUri!.AbsolutePath);
    }

    [Fact]
    public async Task TestGetSchedulerStatusAsync_Success()
    {
        var cannedJson = """
        {
            "status": "registered",
            "is_registered": true,
            "review_task_name": "MagangLog-Review",
            "resume_task_name": "MagangLog-Resume",
            "review_time": "16:30",
            "resume_time": "20:00",
            "diagnostic_message": "Tugas otomatis aktif terdaftar."
        }
        """;

        var handler = new MockHttpMessageHandler(cannedJson);
        var client = new BackendApiClient(new HttpClient(handler));

        var status = await client.GetSchedulerStatusAsync("MagangLog");

        Assert.NotNull(status);
        Assert.Equal("registered", status.Status);
        Assert.True(status.IsRegistered);
        Assert.Equal("16:30", status.ReviewTime);
        Assert.Equal("20:00", status.ResumeTime);
        Assert.Single(handler.SentRequests);
        Assert.Equal(HttpMethod.Get, handler.SentRequests[0].Method);
        Assert.EndsWith("/api/setup/scheduler-status", handler.SentRequests[0].RequestUri!.AbsolutePath);
    }

    [Fact]
    public async Task TestRegisterSchedulerAsync_Success()
    {
        var cannedJson = """
        {
            "success": true,
            "task_name": "MagangLog-Review",
            "review_time": "16:30",
            "resume_time": "20:00"
        }
        """;

        var handler = new MockHttpMessageHandler(cannedJson);
        var client = new BackendApiClient(new HttpClient(handler));

        var req = new RegisterSchedulerRequest
        {
            ReviewTime = "16:30",
            ResumeTime = "20:00",
            TaskPrefix = "MagangLog"
        };

        var response = await client.RegisterSchedulerAsync(req);

        Assert.NotNull(response);
        Assert.True(response.Success);
        Assert.Equal("16:30", response.ReviewTime);
        Assert.Equal("20:00", response.ResumeTime);
        Assert.Single(handler.SentRequests);
        Assert.Equal(HttpMethod.Post, handler.SentRequests[0].Method);
        Assert.EndsWith("/api/setup/register-scheduler", handler.SentRequests[0].RequestUri!.AbsolutePath);
    }

    [Fact]
    public async Task TestUnregisterSchedulerAsync_Success()
    {
        var cannedJson = """
        {
            "success": true,
            "message": "Tugas terjadwal berhasil dihapus."
        }
        """;

        var handler = new MockHttpMessageHandler(cannedJson);
        var client = new BackendApiClient(new HttpClient(handler));

        var response = await client.UnregisterSchedulerAsync("MagangLog");

        Assert.NotNull(response);
        Assert.True(response.Success);
        Assert.Contains("berhasil dihapus", response.Message);
        Assert.Single(handler.SentRequests);
        Assert.Equal(HttpMethod.Post, handler.SentRequests[0].Method);
        Assert.EndsWith("/api/setup/unregister-scheduler", handler.SentRequests[0].RequestUri!.AbsolutePath);
    }
}

