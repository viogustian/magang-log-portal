using System.Threading;
using MagangLog.Desktop.Forms;
using MagangLog.Desktop.Models;
using MagangLog.Desktop.Services;
using Xunit;

namespace MagangLog.Desktop.Tests;

public class SetupWizardDialogStep6Tests
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

    private static BackendApiClient CreateMockClient(out MockHttpMessageHandler handler)
    {
        handler = new MockHttpMessageHandler("""{"success": true, "saved_at": "2026-11-09T22:00:00Z"}""");
        return new BackendApiClient(new HttpClient(handler));
    }

    [Fact]
    public async Task SetupWizardDialog_Step6_DisplaysSelesaiButtonAndSummary()
    {
        await RunStaAsync(() =>
        {
            var dialog = new SetupWizardDialog(CreateMockClient(out _));
            var state = new WizardProgressState
            {
                CurrentStep = 5,
                CompletedSteps = new List<int> { 0, 1, 2, 3, 4 },
                ProjectFolders = new List<string> { @"C:\Projects\app" },
                ProfileName = "Backend Developer",
                Keywords = new List<string> { "Code.exe", "dotnet.exe" },
                Sources = new SourcesConfig
                {
                    GitFrequency = "sering",
                    GitEnabled = true,
                    AppEnabled = true,
                    BrowserEnabled = false
                },
                ReviewMode = "review"
            };

            dialog.ApplyProgressState(state);

            Assert.Equal(5, dialog.CurrentStep);
            Assert.Equal("Selesai", dialog.NextButton.Text);
            Assert.True(dialog.NextButton.Enabled);
            Assert.Contains("Backend Developer", dialog.SummaryPanel.RoleSummaryText);

            dialog.Dispose();
            return Task.CompletedTask;
        });
    }

    [Fact]
    public async Task SetupWizardDialog_Step6_UbahButtonRoutesToStepAndReturnsToStep6()
    {
        await RunStaAsync(async () =>
        {
            var dialog = new SetupWizardDialog(CreateMockClient(out _));
            var state = new WizardProgressState
            {
                CurrentStep = 5,
                CompletedSteps = new List<int> { 0, 1, 2, 3, 4 },
                ProjectFolders = new List<string> { @"C:\Projects\app" },
                ProfileName = "Software Engineer",
                Keywords = new List<string> { "Code.exe" },
                Sources = new SourcesConfig { GitFrequency = "sering" },
                ReviewMode = "review"
            };
            dialog.ApplyProgressState(state);

            // Click "Ubah" on Job Role (step index 2)
            dialog.SummaryPanel.TriggerEditSection(2);

            Assert.Equal(2, dialog.CurrentStep);

            // Change profile name in step 2
            dialog.RolePanel.KeywordPanel.ProfileName = "Senior Engineer";

            // Click "Lanjut" from step 2 -> should immediately return back to Step 5 (Step 6)
            await dialog.HandleNextClickAsync();

            Assert.Equal(5, dialog.CurrentStep);
            Assert.Equal("Senior Engineer", dialog.State.ProfileName);
            Assert.Contains("Senior Engineer", dialog.SummaryPanel.RoleSummaryText);

            dialog.Dispose();
        });
    }

    [Fact]
    public async Task SetupWizardDialog_Step6_Selesai_SavesConfigAndCompletesWizard()
    {
        await RunStaAsync(async () =>
        {
            var client = CreateMockClient(out var handler);
            var dialog = new SetupWizardDialog(client);
            var state = new WizardProgressState
            {
                CurrentStep = 5,
                CompletedSteps = new List<int> { 0, 1, 2, 3, 4 },
                ProjectFolders = new List<string> { @"C:\Projects\app" },
                ProfileName = "Software Engineer",
                Keywords = new List<string> { "Code.exe", "git.exe" },
                Sources = new SourcesConfig
                {
                    GitFrequency = "sering",
                    GitEnabled = true,
                    AppEnabled = true,
                    BrowserEnabled = false
                },
                ReviewMode = "review"
            };
            dialog.ApplyProgressState(state);

            // Click "Selesai" (HandleNextClickAsync on Step 5)
            await dialog.HandleNextClickAsync();

            Assert.Equal(DialogResult.OK, dialog.DialogResult);
            Assert.Contains(5, dialog.State.CompletedSteps);

            // Check that POST /api/setup/save was called
            var saveCall = handler.SentRequests.Find(r => r.RequestUri != null && r.RequestUri.AbsolutePath.EndsWith("/api/setup/save"));
            Assert.NotNull(saveCall);
            Assert.Equal(HttpMethod.Post, saveCall.Method);

            dialog.Dispose();
        });
    }
}
