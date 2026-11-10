using System.Threading;
using MagangLog.Desktop.Controls;
using MagangLog.Desktop.Models;
using Xunit;

namespace MagangLog.Desktop.Tests;

public class SummaryPanelTests
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
    public async Task SummaryPanel_RefreshSummary_DisplaysAllSections()
    {
        await RunStaAsync(() =>
        {
            var panel = new SummaryPanel();
            var state = new WizardProgressState
            {
                ProjectFolders = new List<string> { @"C:\Projects\app1" },
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

            panel.RefreshSummary(state);

            Assert.Contains(@"C:\Projects\app1", panel.FoldersSummaryText);
            Assert.Contains("Software Engineer", panel.RoleSummaryText);
            Assert.Contains("Code.exe", panel.RoleSummaryText);
            Assert.Contains("Sering", panel.SourcesSummaryText);
            Assert.Contains("Review Dulu", panel.SubmissionSummaryText);

            panel.Dispose();
            return Task.CompletedTask;
        });
    }

    [Fact]
    public async Task SummaryPanel_ClickingUbah_FiresEditSectionRequestedWithCorrectStep()
    {
        await RunStaAsync(() =>
        {
            var panel = new SummaryPanel();
            int? requestedStep = null;
            panel.EditSectionRequested += (_, step) => requestedStep = step;

            // Trigger edit on Folders (Step 1)
            panel.TriggerEditSection(1);
            Assert.Equal(1, requestedStep);

            // Trigger edit on Role (Step 2)
            panel.TriggerEditSection(2);
            Assert.Equal(2, requestedStep);

            // Trigger edit on Sources (Step 3)
            panel.TriggerEditSection(3);
            Assert.Equal(3, requestedStep);

            // Trigger edit on Submission (Step 4)
            panel.TriggerEditSection(4);
            Assert.Equal(4, requestedStep);

            panel.Dispose();
            return Task.CompletedTask;
        });
    }
}
