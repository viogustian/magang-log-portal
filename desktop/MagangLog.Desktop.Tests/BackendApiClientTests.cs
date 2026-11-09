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
}

