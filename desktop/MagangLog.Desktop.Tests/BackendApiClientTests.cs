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
}

