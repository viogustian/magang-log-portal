using System.Net;
using MagangLog.Desktop.Forms;
using MagangLog.Desktop.Models;
using MagangLog.Desktop.Services;
using Xunit;

namespace MagangLog.Desktop.Tests;

public class SetupWizardDialogTests
{
    private static void RunSta(Action action)
    {
        Exception? ex = null;
        var thread = new Thread(() =>
        {
            try
            {
                action();
            }
            catch (Exception e)
            {
                ex = e;
            }
        });
        thread.SetApartmentState(ApartmentState.STA);
        thread.Start();
        thread.Join();

        if (ex != null)
        {
            System.Runtime.ExceptionServices.ExceptionDispatchInfo.Capture(ex).Throw();
        }
    }

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
    public void TestInitialDialogConfigurationAndPanelCount()
    {
        RunSta(() =>
        {
            var handler = new MockHttpMessageHandler("""{"current_step": 0, "completed_steps": [], "step_data": {}}""");
            var client = new BackendApiClient(new HttpClient(handler));

            using var dialog = new SetupWizardDialog(client);

            Assert.Equal(6, dialog.StepCount);
            Assert.Equal(0, dialog.CurrentStep);
            Assert.False(dialog.BackButton.Enabled);
            Assert.Equal("Lanjut", dialog.NextButton.Text);
            // On step 0, NextButton is disabled until system requirements pass the gate
            Assert.False(dialog.NextButton.Enabled);
        });
    }

    [Fact]
    public void TestPanelSwitchingAndNavigationControls()
    {
        RunSta(() =>
        {
            var handler = new MockHttpMessageHandler("""{"current_step": 0, "completed_steps": [], "step_data": {}}""");
            var client = new BackendApiClient(new HttpClient(handler));

            using var dialog = new SetupWizardDialog(client);

            // Navigate to step 1
            dialog.GoToStep(1);
            Assert.Equal(1, dialog.CurrentStep);
            Assert.True(dialog.BackButton.Enabled);
            Assert.Equal("Lanjut", dialog.NextButton.Text);

            // Navigate to final step (5)
            dialog.GoToStep(5);
            Assert.Equal(5, dialog.CurrentStep);
            Assert.True(dialog.BackButton.Enabled);
            Assert.Equal("Selesai", dialog.NextButton.Text);

            // Navigate back to step 0
            dialog.GoToStep(0);
            Assert.Equal(0, dialog.CurrentStep);
            Assert.False(dialog.BackButton.Enabled);
            Assert.Equal("Lanjut", dialog.NextButton.Text);
        });
    }

    [Fact]
    public void TestResumeFromSavedProgress()
    {
        RunSta(() =>
        {
            var savedJson = """
            {
                "current_step": 3,
                "completed_steps": [0, 1, 2],
                "step_data": {
                    "role": "UI/UX Designer"
                }
            }
            """;

            var handler = new MockHttpMessageHandler(savedJson);
            var client = new BackendApiClient(new HttpClient(handler));

            using var dialog = new SetupWizardDialog(client);
            dialog.ApplyProgressState(new WizardProgressState
            {
                CurrentStep = 3,
                CompletedSteps = new List<int> { 0, 1, 2 },
                StepData = new Dictionary<string, object?> { ["role"] = "UI/UX Designer" }
            });

            Assert.Equal(3, dialog.CurrentStep);
            Assert.True(dialog.BackButton.Enabled);
            Assert.Equal("Lanjut", dialog.NextButton.Text);
            Assert.Contains(0, dialog.State.CompletedSteps);
            Assert.Contains(1, dialog.State.CompletedSteps);
            Assert.Contains(2, dialog.State.CompletedSteps);
        });
    }

    [Fact]
    public void TestStepIndicatorUpdates()
    {
        RunSta(() =>
        {
            var handler = new MockHttpMessageHandler("""{"current_step": 0, "completed_steps": [], "step_data": {}}""");
            var client = new BackendApiClient(new HttpClient(handler));

            using var dialog = new SetupWizardDialog(client);
            var indicator = dialog.StepIndicator;

            Assert.NotNull(indicator);
            Assert.Equal(6, indicator.StepCount);

            dialog.GoToStep(2);
            Assert.Equal(2, indicator.CurrentStep);
        });
    }

    [Fact]
    public async Task TestHandleNextClickAdvancesAndSavesProgress()
    {
        await RunStaAsync(async () =>
        {
            var handler = new MockHttpMessageHandler("""{"success": true, "saved_at": "2026-11-09T22:00:00Z"}""");
            var client = new BackendApiClient(new HttpClient(handler));

            using var dialog = new SetupWizardDialog(client);
            Assert.Equal(0, dialog.CurrentStep);

            // Trigger next click asynchronously
            await dialog.HandleNextClickAsync();

            Assert.Equal(1, dialog.CurrentStep);
            Assert.Contains(0, dialog.State.CompletedSteps);
            Assert.Equal(1, dialog.State.CurrentStep);
            Assert.NotEmpty(handler.SentRequests);
        });
    }
}
