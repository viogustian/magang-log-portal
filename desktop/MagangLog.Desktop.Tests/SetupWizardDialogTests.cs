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

    [Fact]
    public void TestWizardLayout_HeaderAndNavDoNotOverlapStepContent()
    {
        RunSta(() =>
        {
            var handler = new MockHttpMessageHandler("""{"current_step": 0, "completed_steps": [], "step_data": {}}""");
            var client = new BackendApiClient(new HttpClient(handler));

            using var dialog = new SetupWizardDialog(client);
            dialog.CreateControl();
            dialog.PerformLayout();

            var indicator = dialog.StepIndicator;
            var contentContainer = dialog.StepPanels[0].Parent!;
            var navPanel = dialog.BackButton.Parent!;

            Assert.True(
                contentContainer.Top >= indicator.Bottom,
                $"Content container Top ({contentContainer.Top}) overlaps StepIndicator Bottom ({indicator.Bottom}).");
            Assert.True(
                contentContainer.Bottom <= navPanel.Top,
                $"Content container Bottom ({contentContainer.Bottom}) overlaps navPanel Top ({navPanel.Top}).");

            Control[] hostedPanels =
            [
                dialog.GeminiCard,
                dialog.FolderPanel,
                dialog.RolePanel,
                dialog.FrequencyPanel,
                dialog.SubmissionModePanel,
                dialog.SummaryPanel
            ];

            for (int step = 0; step < dialog.StepCount; step++)
            {
                dialog.GoToStep(step);
                dialog.PerformLayout();

                var stepPanel = dialog.StepPanels[step];
                stepPanel.PerformLayout();

                var labels = stepPanel.Controls.OfType<Label>().OrderBy(l => l.Top).ToList();
                Assert.True(labels.Count >= 2, $"Step {step} expected title and subtitle labels.");
                var titleLabel = labels[0];
                var subtitleLabel = labels[1];

                Assert.True(titleLabel.Top >= 0, $"Step {step} title Top ({titleLabel.Top}) < 0.");
                Assert.True(
                    subtitleLabel.Top >= titleLabel.Bottom,
                    $"Step {step} subtitle Top ({subtitleLabel.Top}) < title Bottom ({titleLabel.Bottom}).");
                Assert.True(
                    hostedPanels[step].Top >= subtitleLabel.Bottom,
                    $"Step {step} hosted panel Top ({hostedPanels[step].Top}) < subtitle Bottom ({subtitleLabel.Bottom}).");
            }

            // Step 0 additionally stacks RequirementListPanel below GeminiCredentialsCard
            dialog.GoToStep(0);
            dialog.StepPanels[0].PerformLayout();
            Assert.True(
                dialog.RequirementPanel.Top >= dialog.GeminiCard.Bottom,
                $"RequirementPanel Top ({dialog.RequirementPanel.Top}) < GeminiCard Bottom ({dialog.GeminiCard.Bottom}).");
        });
    }

    [Fact]
    public void TestStepIndicator_AllLabelsFitWithoutWrappingOrVerticalMisalignment()
    {
        RunSta(() =>
        {
            var handler = new MockHttpMessageHandler("""{"current_step": 0, "completed_steps": [], "step_data": {}}""");
            var client = new BackendApiClient(new HttpClient(handler));

            using var dialog = new SetupWizardDialog(client);
            dialog.CreateControl();
            dialog.PerformLayout();

            // Verify at default size and minimum width across every active step (0..5)
            foreach (var testWidth in new[] { dialog.Width, dialog.MinimumSize.Width })
            {
                dialog.Width = testWidth;
                dialog.PerformLayout();

                for (int activeStep = 0; activeStep < dialog.StepCount; activeStep++)
                {
                    var completed = Enumerable.Range(0, activeStep).ToArray();
                    dialog.StepIndicator.UpdateStep(activeStep, completed);
                    dialog.StepIndicator.PerformLayout();

                    var table = dialog.StepIndicator.Controls.OfType<TableLayoutPanel>().Single();
                    var labels = table.Controls.OfType<Label>().OrderBy(l => l.Left).ToList();
                    Assert.Equal(6, labels.Count);

                    var expectedTop = labels[0].Top;
                    var expectedHeight = labels[0].Height;
                    foreach (var lbl in labels)
                    {
                        Assert.Equal(expectedTop, lbl.Top);
                        Assert.Equal(expectedHeight, lbl.Height);
                        Assert.False(lbl.UseMnemonic);

                        var singleLineSize = TextRenderer.MeasureText(
                            lbl.Text,
                            lbl.Font,
                            new Size(int.MaxValue, int.MaxValue),
                            TextFormatFlags.SingleLine | TextFormatFlags.NoPrefix);

                        Assert.True(
                            singleLineSize.Width <= lbl.ClientSize.Width - lbl.Padding.Horizontal,
                            $"At width={testWidth}, step={activeStep}, label '{lbl.Text}' width ({singleLineSize.Width}px) exceeds inner cell width ({lbl.ClientSize.Width - lbl.Padding.Horizontal}px).");
                        Assert.True(
                            singleLineSize.Height <= lbl.ClientSize.Height,
                            $"At width={testWidth}, step={activeStep}, label '{lbl.Text}' height ({singleLineSize.Height}px) exceeds cell height ({lbl.ClientSize.Height}px).");
                    }
                }
            }
        });
    }
}
