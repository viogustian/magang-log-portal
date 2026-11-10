using System.Threading;
using MagangLog.Desktop.Controls;
using MagangLog.Desktop.Models;
using MagangLog.Desktop.Services;
using Xunit;

namespace MagangLog.Desktop.Tests;

public class JobRolePanelTests
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
    public async Task PredictKeywordsAsync_Success_PopulatesKeywordPanel()
    {
        await RunStaAsync(async () =>
        {
            var cannedJson = """
            {
                "source": "gemini",
                "profile": {
                    "profile_name": "Software Engineer",
                    "natural_description": "Coding in C# and TypeScript",
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
            var apiClient = new BackendApiClient(httpClient);

            var panel = new JobRolePanel(apiClient);
            panel.Description = "Coding backend APIs";

            await panel.PredictKeywordsAsync();

            Assert.Equal("Software Engineer", panel.KeywordPanel.ProfileName);
            Assert.Contains("Code.exe", panel.KeywordPanel.Keywords);
            Assert.True(panel.HasValidProfile);
            Assert.False(panel.IsWarningBannerVisible);

            panel.Dispose();
        });
    }

    [Fact]
    public async Task PredictKeywordsAsync_Failure_ShowsWarningBannerAndKeepsManualMode()
    {
        await RunStaAsync(async () =>
        {
            // Simulating 500 error from backend
            var handler = new MockHttpMessageHandler("Internal error", System.Net.HttpStatusCode.InternalServerError);
            var httpClient = new HttpClient(handler);
            var apiClient = new BackendApiClient(httpClient);

            var panel = new JobRolePanel(apiClient);
            panel.Description = "Some arbitrary task";

            await panel.PredictKeywordsAsync();

            Assert.True(panel.IsWarningBannerVisible);
            Assert.Contains("Gagal", panel.WarningBannerText);

            // Manual entry still works seamlessly
            panel.KeywordPanel.ProfileName = "Custom Role";
            panel.KeywordPanel.AddKeyword("mytool.exe");

            Assert.True(panel.HasValidProfile);
            Assert.Single(panel.KeywordPanel.Keywords);

            panel.Dispose();
        });
    }

    [Fact]
    public async Task LoadPresetsAsync_PopulatesDropdownAndSelectingAppliesProfile()
    {
        await RunStaAsync(async () =>
        {
            var cannedJson = """
            [
                {
                    "profile_name": "UI/UX Designer",
                    "natural_description": "Designing user interfaces and wireframes",
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
            var apiClient = new BackendApiClient(httpClient);

            var panel = new JobRolePanel(apiClient);
            await panel.LoadPresetsAsync();

            Assert.True(panel.PresetCount > 0);

            // Select preset by name
            panel.SelectPresetByName("UI/UX Designer");

            Assert.Equal("UI/UX Designer", panel.KeywordPanel.ProfileName);
            Assert.Contains("Figma.exe", panel.KeywordPanel.Keywords);
            Assert.True(panel.HasValidProfile);

            panel.Dispose();
        });
    }
}

