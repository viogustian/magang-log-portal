#pragma warning disable xUnit1031

using System.Net;
using System.Text.Json;
using MagangLog.Desktop.Forms;
using MagangLog.Desktop.Models;
using MagangLog.Desktop.Services;
using Xunit;

namespace MagangLog.Desktop.Tests;

public class SetupWizardDialogStep1GeminiTests
{
    private static async Task RunStaAsync(Func<Task> action)
    {
        var tcs = new TaskCompletionSource();
        var thread = new Thread(async () =>
        {
            try
            {
                await action();
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

    private static string BuildOkRequirementsJson() => """
    [
        {
            "name": "Python",
            "min_version": ">=3.12",
            "installed_version": "3.12.0",
            "status": "ok",
            "guidance": {}
        }
    ]
    """;

    [Fact]
    public async Task SetupWizard_Step1_EmptyGeminiKeyBlocksGate()
    {
        await RunStaAsync(async () =>
        {
            var handler = new MockHttpMessageHandler(BuildOkRequirementsJson());
            var client = new BackendApiClient(new HttpClient(handler));

            using var dialog = new SetupWizardDialog(client);
            await dialog.RequirementPanel.LoadRequirementsAsync();

            dialog.GeminiApiKey = string.Empty;
            dialog.EvaluateGateState();

            Assert.False(dialog.NextButton.Enabled);
            Assert.Contains("Google AI Studio API Key", dialog.StatusLabel.Text);
        });
    }

    [Fact]
    public async Task SetupWizard_Step1_SupplyingGeminiKeyEnablesGate()
    {
        await RunStaAsync(async () =>
        {
            var handler = new MockHttpMessageHandler(BuildOkRequirementsJson());
            var client = new BackendApiClient(new HttpClient(handler));

            using var dialog = new SetupWizardDialog(client);
            await dialog.RequirementPanel.LoadRequirementsAsync();

            dialog.GeminiApiKey = "AIzaSyTestValid12345";
            dialog.EvaluateGateState();

            Assert.True(dialog.NextButton.Enabled);
            Assert.Contains("siap", dialog.StatusLabel.Text.ToLower());
        });
    }

    [Fact]
    public async Task SetupWizard_Step1_AdvancingToStep2_SavesKeyAndModelToState()
    {
        await RunStaAsync(async () =>
        {
            var handler = new MockHttpMessageHandler("""{"success": true, "saved_at": "2026-11-10T00:00:00Z"}""");
            var client = new BackendApiClient(new HttpClient(handler));

            using var dialog = new SetupWizardDialog(client);
            dialog.GeminiApiKey = "AIzaSyOnboardingKey";
            dialog.GeminiCard.SelectedModel = "gemini-3.8-flash";

            await dialog.HandleNextClickAsync();

            Assert.Equal(1, dialog.CurrentStep);
            Assert.Equal("AIzaSyOnboardingKey", dialog.State.GeminiApiKey);
            Assert.Equal("gemini-3.8-flash", dialog.State.GeminiModel);
        });
    }

    [Fact]
    public async Task SetupWizard_Step1_PropagatesKeyToRolePanelForPrediction()
    {
        await RunStaAsync(async () =>
        {
            string? capturedApiKey = null;
            var handler = new MockHttpMessageHandler(req =>
            {
                if (req.RequestUri!.AbsolutePath.EndsWith("/predict-profile"))
                {
                    var body = req.Content!.ReadAsStringAsync().GetAwaiter().GetResult();
                    var parsed = JsonSerializer.Deserialize<PredictProfileRequest>(body, new JsonSerializerOptions { PropertyNameCaseInsensitive = true });
                    capturedApiKey = parsed?.ApiKey;

                    var respJson = """
                    {
                        "source": "gemini",
                        "profile": {
                            "profile_name": "Software Engineer",
                            "natural_description": "Coding",
                            "applications": [
                                {
                                    "name": "VS Code",
                                    "process_names": ["Code.exe"],
                                    "file_extensions": [".cs"]
                                }
                            ]
                        }
                    }
                    """;
                    return new HttpResponseMessage(HttpStatusCode.OK)
                    {
                        Content = new StringContent(respJson, System.Text.Encoding.UTF8, "application/json")
                    };
                }
                return new HttpResponseMessage(HttpStatusCode.OK);
            });

            var client = new BackendApiClient(new HttpClient(handler));
            using var dialog = new SetupWizardDialog(client);

            // Step 1: Input API Key
            dialog.GeminiApiKey = "AIzaSyKeyForPrediction";
            await dialog.HandleNextClickAsync(); // Advances to Step 1 (Folders)

            // Step 2: Advances to Step 2 (Role)
            dialog.GoToStep(2);

            dialog.RolePanel.Description = "Developing backend APIs";
            await dialog.RolePanel.PredictKeywordsAsync();

            Assert.Equal("AIzaSyKeyForPrediction", capturedApiKey);
            Assert.Equal("Software Engineer", dialog.RolePanel.KeywordPanel.ProfileName);
        });
    }

    [Fact]
    public async Task SetupWizard_Step6_PersistsGeminiKeyToSaveConfig()
    {
        await RunStaAsync(async () =>
        {
            string? capturedPayload = null;
            var handler = new MockHttpMessageHandler(req =>
            {
                if (req.RequestUri!.AbsolutePath.EndsWith("/save"))
                {
                    capturedPayload = req.Content!.ReadAsStringAsync().GetAwaiter().GetResult();
                    return new HttpResponseMessage(HttpStatusCode.OK)
                    {
                        Content = new StringContent("""{"success": true, "saved_at": "2026-11-10T00:00:00Z"}""", System.Text.Encoding.UTF8, "application/json")
                    };
                }
                return new HttpResponseMessage(HttpStatusCode.OK)
                {
                    Content = new StringContent("""{"success": true}""", System.Text.Encoding.UTF8, "application/json")
                };
            });

            var client = new BackendApiClient(new HttpClient(handler));
            using var dialog = new SetupWizardDialog(client);

            dialog.State.GeminiApiKey = "AIzaSyPersistedFinalKey";
            dialog.State.GeminiModel = "gemini-3.5-flash";
            dialog.State.ProjectFolders = new List<string> { @"C:\Repo" };
            dialog.State.ProfileName = "Engineer";
            dialog.State.Keywords = new List<string> { "Code.exe" };

            // Jump to final step (5)
            dialog.GoToStep(5);
            await dialog.HandleNextClickAsync();

            Assert.NotNull(capturedPayload);
            Assert.Contains("AIzaSyPersistedFinalKey", capturedPayload);
            Assert.Contains("gemini-3.5-flash", capturedPayload);
        });
    }
}
