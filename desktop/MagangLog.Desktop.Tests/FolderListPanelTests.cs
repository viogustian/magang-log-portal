using MagangLog.Desktop.Controls;
using MagangLog.Desktop.Forms;
using MagangLog.Desktop.Models;
using MagangLog.Desktop.Services;
using Xunit;

namespace MagangLog.Desktop.Tests;

public class FolderListPanelTests
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

    [Fact]
    public async Task TestAddValidFolderUpdatesListAndEnablesGate()
    {
        await RunStaAsync(async () =>
        {
            var cannedJson = """
            [
                {
                    "path": "C:\\Projects\\App1",
                    "exists": true,
                    "readable": true,
                    "is_git": true,
                    "error": null
                }
            ]
            """;

            var handler = new MockHttpMessageHandler(cannedJson);
            var client = new BackendApiClient(new HttpClient(handler));

            using var dialog = new SetupWizardDialog(client);
            dialog.GoToStep(1); // Navigate to Step 2 (Folder Proyek)

            var panel = dialog.FolderPanel;
            Assert.NotNull(panel);
            Assert.False(panel.HasValidFolders);
            Assert.False(dialog.NextButton.Enabled);

            await panel.AddFolderAsync("C:\\Projects\\App1");

            Assert.True(panel.HasValidFolders);
            Assert.Single(panel.Folders);
            Assert.True(panel.Folders[0].IsGit);
            Assert.True(dialog.NextButton.Enabled);
            Assert.Contains("valid", dialog.StatusLabel.Text.ToLower());
        });
    }

    [Fact]
    public async Task TestAddInvalidFolderShowsErrorAndKeepsGateDisabled()
    {
        await RunStaAsync(async () =>
        {
            var cannedJson = """
            [
                {
                    "path": "C:\\Projects\\MissingDir",
                    "exists": false,
                    "readable": false,
                    "is_git": false,
                    "error": "Folder tidak ditemukan"
                }
            ]
            """;

            var handler = new MockHttpMessageHandler(cannedJson);
            var client = new BackendApiClient(new HttpClient(handler));

            using var dialog = new SetupWizardDialog(client);
            dialog.GoToStep(1);

            var panel = dialog.FolderPanel;
            await panel.AddFolderAsync("C:\\Projects\\MissingDir");

            Assert.False(panel.HasValidFolders);
            Assert.Single(panel.Folders);
            Assert.False(panel.Folders[0].Exists);
            Assert.Equal("Folder tidak ditemukan", panel.Folders[0].Error);
            Assert.False(dialog.NextButton.Enabled);
            Assert.Contains("minimal satu folder", dialog.StatusLabel.Text.ToLower());
        });
    }

    [Fact]
    public async Task TestRemoveFolderReevaluatesGate()
    {
        await RunStaAsync(async () =>
        {
            var cannedJson = """
            [
                {
                    "path": "C:\\Projects\\App1",
                    "exists": true,
                    "readable": true,
                    "is_git": false,
                    "error": null
                }
            ]
            """;

            var handler = new MockHttpMessageHandler(cannedJson);
            var client = new BackendApiClient(new HttpClient(handler));

            using var dialog = new SetupWizardDialog(client);
            dialog.GoToStep(1);

            var panel = dialog.FolderPanel;
            await panel.AddFolderAsync("C:\\Projects\\App1");
            Assert.True(panel.HasValidFolders);
            Assert.True(dialog.NextButton.Enabled);

            // Remove the folder
            panel.RemoveFolder("C:\\Projects\\App1");
            Assert.False(panel.HasValidFolders);
            Assert.Empty(panel.Folders);
            Assert.False(dialog.NextButton.Enabled);
        });
    }

    [Fact]
    public async Task TestAdvanceStepPreservesFoldersInState()
    {
        await RunStaAsync(async () =>
        {
            var cannedValidateJson = """
            [
                {
                    "path": "C:\\Projects\\App1",
                    "exists": true,
                    "readable": true,
                    "is_git": true,
                    "error": null
                }
            ]
            """;

            var handler = new MockHttpMessageHandler(req =>
            {
                if (req.RequestUri!.AbsolutePath.EndsWith("/validate-folders"))
                {
                    return new HttpResponseMessage(System.Net.HttpStatusCode.OK)
                    {
                        Content = new StringContent(cannedValidateJson, System.Text.Encoding.UTF8, "application/json")
                    };
                }
                return new HttpResponseMessage(System.Net.HttpStatusCode.OK)
                {
                    Content = new StringContent("""{"success": true, "saved_at": "2026-11-09T22:00:00Z"}""", System.Text.Encoding.UTF8, "application/json")
                };
            });

            var client = new BackendApiClient(new HttpClient(handler));

            using var dialog = new SetupWizardDialog(client);
            dialog.GoToStep(1);

            await dialog.FolderPanel.AddFolderAsync("C:\\Projects\\App1");
            Assert.True(dialog.NextButton.Enabled);

            await dialog.HandleNextClickAsync();

            Assert.Equal(2, dialog.CurrentStep);
            Assert.Contains("C:\\Projects\\App1", dialog.State.ProjectFolders);
        });
    }
}

