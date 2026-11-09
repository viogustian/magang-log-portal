using System.Threading;
using MagangLog.Desktop.Forms;
using MagangLog.Desktop.Models;
using MagangLog.Desktop.Services;
using Xunit;

namespace MagangLog.Desktop.Tests;

public class SetupWizardDialogStep4Tests
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
    public async Task SetupWizardDialog_Step4_GateEnforcement()
    {
        await RunStaAsync(() =>
        {
            var dialog = new SetupWizardDialog(CreateMockClient());
            dialog.GoToStep(3);

            // Default 'Sering' has Git and App enabled -> gate enabled
            Assert.True(dialog.NextButton.Enabled);

            // Set 'tidak_sama_sekali', and uncheck all consents -> gate disabled
            dialog.FrequencyPanel.SetFrequency("tidak_sama_sekali");
            dialog.FrequencyPanel.AppConsent = false;
            dialog.FrequencyPanel.BrowserConsent = false;
            dialog.EvaluateGateState();

            Assert.False(dialog.NextButton.Enabled);
            Assert.Contains("minimal satu sumber", dialog.StatusLabel.Text);

            // Check App consent -> gate enabled again
            dialog.FrequencyPanel.AppConsent = true;
            dialog.EvaluateGateState();
            Assert.True(dialog.NextButton.Enabled);

            dialog.Dispose();
            return Task.CompletedTask;
        });
    }

    [Fact]
    public async Task SetupWizardDialog_Step4_NextClick_SavesSourcesToState()
    {
        await RunStaAsync(async () =>
        {
            var dialog = new SetupWizardDialog(CreateMockClient());
            dialog.GoToStep(3);

            dialog.FrequencyPanel.SetFrequency("jarang");
            dialog.FrequencyPanel.AppConsent = true;
            dialog.FrequencyPanel.BrowserConsent = true;

            await dialog.HandleNextClickAsync();

            Assert.Equal(4, dialog.CurrentStep);
            Assert.Contains(3, dialog.State.CompletedSteps);
            Assert.NotNull(dialog.State.Sources);
            Assert.Equal("jarang", dialog.State.Sources.GitFrequency);
            Assert.True(dialog.State.Sources.GitEnabled);
            Assert.True(dialog.State.Sources.AppEnabled);
            Assert.True(dialog.State.Sources.BrowserEnabled);

            dialog.Dispose();
        });
    }

    [Fact]
    public async Task SetupWizardDialog_ApplyProgressState_RestoresStep4Sources()
    {
        await RunStaAsync(() =>
        {
            var dialog = new SetupWizardDialog(CreateMockClient());
            var state = new WizardProgressState
            {
                CurrentStep = 3,
                CompletedSteps = new List<int> { 0, 1, 2 },
                Sources = new SourcesConfig
                {
                    GitFrequency = "tidak_sama_sekali",
                    GitEnabled = false,
                    AppEnabled = true,
                    BrowserEnabled = true,
                    AppConsent = true,
                    BrowserConsent = true
                }
            };

            dialog.ApplyProgressState(state);

            Assert.Equal(3, dialog.CurrentStep);
            Assert.Equal("tidak_sama_sekali", dialog.FrequencyPanel.GitFrequency);
            Assert.False(dialog.FrequencyPanel.GitEnabled);
            Assert.True(dialog.FrequencyPanel.BrowserEnabled);
            Assert.True(dialog.NextButton.Enabled);

            dialog.Dispose();
            return Task.CompletedTask;
        });
    }
}

