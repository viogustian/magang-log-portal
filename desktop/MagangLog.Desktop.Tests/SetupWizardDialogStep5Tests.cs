using System.Threading;
using MagangLog.Desktop.Forms;
using MagangLog.Desktop.Models;
using MagangLog.Desktop.Services;
using Xunit;

namespace MagangLog.Desktop.Tests;

public class SetupWizardDialogStep5Tests
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
    public async Task SetupWizardDialog_Step5_DefaultIsReviewAndGateEnabled()
    {
        await RunStaAsync(() =>
        {
            var dialog = new SetupWizardDialog(CreateMockClient());
            dialog.GoToStep(4);

            Assert.Equal("review", dialog.SubmissionModePanel.ReviewMode);
            Assert.True(dialog.NextButton.Enabled);

            dialog.Dispose();
            return Task.CompletedTask;
        });
    }

    [Fact]
    public async Task SetupWizardDialog_Step5_FullAccessGateEnforcement()
    {
        await RunStaAsync(() =>
        {
            var dialog = new SetupWizardDialog(CreateMockClient());
            dialog.GoToStep(4);

            // Switch to Full Access -> gate disabled
            dialog.SubmissionModePanel.SetMode("auto");
            dialog.EvaluateGateState();

            Assert.False(dialog.NextButton.Enabled);
            Assert.Contains("konfirmasi persetujuan", dialog.StatusLabel.Text);

            // Check confirmation box -> gate enabled
            dialog.SubmissionModePanel.FullAccessConfirmed = true;
            dialog.EvaluateGateState();

            Assert.True(dialog.NextButton.Enabled);

            dialog.Dispose();
            return Task.CompletedTask;
        });
    }

    [Fact]
    public async Task SetupWizardDialog_Step5_NextClick_SavesReviewModeToState()
    {
        await RunStaAsync(async () =>
        {
            var dialog = new SetupWizardDialog(CreateMockClient());
            dialog.GoToStep(4);

            dialog.SubmissionModePanel.SetMode("notify");
            await dialog.HandleNextClickAsync();

            Assert.Equal(5, dialog.CurrentStep);
            Assert.Contains(4, dialog.State.CompletedSteps);
            Assert.Equal("notify", dialog.State.ReviewMode);
            Assert.False(dialog.State.FullAccessConfirmed);

            dialog.Dispose();
        });
    }

    [Fact]
    public async Task SetupWizardDialog_ApplyProgressState_RestoresStep5Mode()
    {
        await RunStaAsync(() =>
        {
            var dialog = new SetupWizardDialog(CreateMockClient());
            var state = new WizardProgressState
            {
                CurrentStep = 4,
                CompletedSteps = new List<int> { 0, 1, 2, 3 },
                ReviewMode = "auto",
                FullAccessConfirmed = true
            };

            dialog.ApplyProgressState(state);

            Assert.Equal(4, dialog.CurrentStep);
            Assert.Equal("auto", dialog.SubmissionModePanel.ReviewMode);
            Assert.True(dialog.SubmissionModePanel.FullAccessConfirmed);
            Assert.True(dialog.NextButton.Enabled);

            dialog.Dispose();
            return Task.CompletedTask;
        });
    }
}

