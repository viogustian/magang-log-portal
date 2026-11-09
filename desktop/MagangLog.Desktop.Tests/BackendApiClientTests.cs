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
}

