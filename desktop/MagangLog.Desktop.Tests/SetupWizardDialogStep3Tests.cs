using System.Threading;
using MagangLog.Desktop.Forms;
using MagangLog.Desktop.Models;
using MagangLog.Desktop.Services;
using Xunit;

namespace MagangLog.Desktop.Tests;

public class SetupWizardDialogStep3Tests
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

    private static BackendApiClient CreateMockClient()
    {
        var handler = new MockHttpMessageHandler("""{"success": true, "saved_at": "2026-11-09T22:00:00Z"}""");
        return new BackendApiClient(new HttpClient(handler));
    }

    [Fact]
    public async Task SetupWizardDialog_Step3_GateEnforcement()
    {
        await RunStaAsync(() =>
        {
            var dialog = new SetupWizardDialog(CreateMockClient());
            dialog.GoToStep(2);

            // Initially empty profile and keywords -> gate disabled
            Assert.False(dialog.NextButton.Enabled);
            Assert.Contains("minimal satu kata kunci", dialog.StatusLabel.Text);

            // Set profile name but no keywords -> gate still disabled
            dialog.RolePanel.KeywordPanel.ProfileName = "Software Engineer";
            dialog.EvaluateGateState();
            Assert.False(dialog.NextButton.Enabled);

            // Add keyword -> gate enabled
            dialog.RolePanel.KeywordPanel.AddKeyword("Code.exe");
            dialog.EvaluateGateState();
            Assert.True(dialog.NextButton.Enabled);

            dialog.Dispose();
            return Task.CompletedTask;
        });
    }

    [Fact]
    public async Task SetupWizardDialog_Step3_NextClick_SavesProfileAndKeywordsToState()
    {
        await RunStaAsync(async () =>
        {
            var dialog = new SetupWizardDialog(CreateMockClient());
            dialog.GoToStep(2);

            dialog.RolePanel.Description = "Developing backend APIs in C#";
            dialog.RolePanel.KeywordPanel.ProfileName = "Backend Developer";
            dialog.RolePanel.KeywordPanel.AddKeyword("dotnet.exe");
            dialog.RolePanel.KeywordPanel.AddKeyword("devenv.exe");

            await dialog.HandleNextClickAsync();

            Assert.Equal(3, dialog.CurrentStep);
            Assert.Contains(2, dialog.State.CompletedSteps);
            Assert.Equal("Developing backend APIs in C#", dialog.State.RoleDescription);
            Assert.Equal("Backend Developer", dialog.State.ProfileName);
            Assert.Equal(2, dialog.State.Keywords.Count);
            Assert.Contains("dotnet.exe", dialog.State.Keywords);
            Assert.Contains("devenv.exe", dialog.State.Keywords);

            dialog.Dispose();
        });
    }

    [Fact]
    public async Task SetupWizardDialog_ApplyProgressState_RestoresStep3Data()
    {
        await RunStaAsync(() =>
        {
            var dialog = new SetupWizardDialog(CreateMockClient());
            var state = new WizardProgressState
            {
                CurrentStep = 2,
                CompletedSteps = new List<int> { 0, 1 },
                RoleDescription = "UI/UX wireframes",
                ProfileName = "UI/UX Designer",
                Keywords = new List<string> { "Figma.exe", "XD.exe" }
            };

            dialog.ApplyProgressState(state);

            Assert.Equal(2, dialog.CurrentStep);
            Assert.Equal("UI/UX wireframes", dialog.RolePanel.Description);
            Assert.Equal("UI/UX Designer", dialog.RolePanel.KeywordPanel.ProfileName);
            Assert.Equal(2, dialog.RolePanel.KeywordPanel.Keywords.Count);
            Assert.Contains("Figma.exe", dialog.RolePanel.KeywordPanel.Keywords);
            Assert.True(dialog.NextButton.Enabled);

            dialog.Dispose();
            return Task.CompletedTask;
        });
    }
}
