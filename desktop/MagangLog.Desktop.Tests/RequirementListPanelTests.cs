using MagangLog.Desktop.Controls;
using MagangLog.Desktop.Forms;
using MagangLog.Desktop.Models;
using MagangLog.Desktop.Services;
using Xunit;

namespace MagangLog.Desktop.Tests;

public class RequirementListPanelTests
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
            catch (Exception e)
            {
                tcs.SetException(e);
            }
        });
        thread.SetApartmentState(ApartmentState.STA);
        thread.Start();
        await tcs.Task;
    }

    private static string BuildCannedRequirementsJson(string playwrightStatus)
    {
        return $$"""
        [
            {
                "name": "Python",
                "min_version": ">=3.12",
                "installed_version": "3.14.8",
                "status": "ok",
                "guidance": {
                    "download_url": "https://www.python.org/downloads/",
                    "install_steps": ["Add Python to PATH"],
                    "verification_command": "python --version",
                    "expected_output": "Python >= 3.12",
                    "troubleshooting": ["Restart terminal"]
                }
            },
            {
                "name": "Playwright",
                "min_version": ">=1.40",
                "installed_version": "{{(playwrightStatus == "ok" ? "1.42.0" : null)}}",
                "status": "{{playwrightStatus}}",
                "guidance": {
                    "download_url": "https://playwright.dev/python/docs/intro",
                    "install_steps": ["pip install playwright", "playwright install chromium"],
                    "verification_command": "playwright --version",
                    "expected_output": "Version 1.40+",
                    "troubleshooting": ["Check execution policy"]
                }
            }
        ]
        """;
    }

    [Fact]
    public async Task TestRequirementsAllOkEnablesGate()
    {
        await RunStaAsync(async () =>
        {
            var json = BuildCannedRequirementsJson("ok");
            var handler = new MockHttpMessageHandler(json);
            var client = new BackendApiClient(new HttpClient(handler));

            using var dialog = new SetupWizardDialog(client);
            var panel = dialog.RequirementPanel;

            Assert.NotNull(panel);
            await panel.LoadRequirementsAsync();

            Assert.True(panel.AllRequirementsSatisfied);
            Assert.True(dialog.NextButton.Enabled);
            Assert.Contains("terpenuhi", dialog.StatusLabel.Text.ToLower());
        });
    }

    [Fact]
    public async Task TestRequirementsWithUnmetItemDisablesGate()
    {
        await RunStaAsync(async () =>
        {
            var json = BuildCannedRequirementsJson("missing");
            var handler = new MockHttpMessageHandler(json);
            var client = new BackendApiClient(new HttpClient(handler));

            using var dialog = new SetupWizardDialog(client);
            var panel = dialog.RequirementPanel;

            Assert.NotNull(panel);
            await panel.LoadRequirementsAsync();

            Assert.False(panel.AllRequirementsSatisfied);
            Assert.False(dialog.NextButton.Enabled);
            Assert.Contains("1 requirement belum terpenuhi", dialog.StatusLabel.Text);
        });
    }

    [Fact]
    public async Task TestRecheckRequirementUpdatesItemAndEnablesGate()
    {
        await RunStaAsync(async () =>
        {
            var initialListJson = BuildCannedRequirementsJson("missing");
            var recheckOkJson = """
            {
                "name": "Playwright",
                "min_version": ">=1.40",
                "installed_version": "1.42.0",
                "status": "ok",
                "guidance": {
                    "download_url": "https://playwright.dev/python/docs/intro",
                    "install_steps": ["pip install playwright"],
                    "verification_command": "playwright --version",
                    "expected_output": "Version 1.40+",
                    "troubleshooting": ["Check PATH"]
                }
            }
            """;

            var handler = new MockHttpMessageHandler(req =>
            {
                if (req.Method == HttpMethod.Get && req.RequestUri!.AbsolutePath.EndsWith("/requirements"))
                {
                    return new HttpResponseMessage(System.Net.HttpStatusCode.OK)
                    {
                        Content = new StringContent(initialListJson, System.Text.Encoding.UTF8, "application/json")
                    };
                }
                if (req.Method == HttpMethod.Post && req.RequestUri!.AbsolutePath.EndsWith("/recheck-requirement"))
                {
                    return new HttpResponseMessage(System.Net.HttpStatusCode.OK)
                    {
                        Content = new StringContent(recheckOkJson, System.Text.Encoding.UTF8, "application/json")
                    };
                }
                return new HttpResponseMessage(System.Net.HttpStatusCode.NotFound);
            });

            var client = new BackendApiClient(new HttpClient(handler));
            using var dialog = new SetupWizardDialog(client);
            var panel = dialog.RequirementPanel;

            await panel.LoadRequirementsAsync();
            Assert.False(panel.AllRequirementsSatisfied);
            Assert.False(dialog.NextButton.Enabled);

            // Re-check single Playwright item
            await panel.RecheckItemAsync("Playwright");

            Assert.True(panel.AllRequirementsSatisfied);
            Assert.True(dialog.NextButton.Enabled);
        });
    }
}

