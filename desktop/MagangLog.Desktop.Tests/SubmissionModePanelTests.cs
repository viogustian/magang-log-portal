using System.Threading;
using MagangLog.Desktop.Controls;
using Xunit;

namespace MagangLog.Desktop.Tests;

public class SubmissionModePanelTests
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
    public async Task SubmissionMode_DefaultIsReviewAndGateSatisfied()
    {
        await RunStaAsync(() =>
        {
            var panel = new SubmissionModePanel();

            Assert.Equal("review", panel.ReviewMode);
            Assert.True(panel.IsGateSatisfied);
            Assert.False(panel.IsFullAccessWarningVisible);

            panel.Dispose();
            return Task.CompletedTask;
        });
    }

    [Fact]
    public async Task SubmissionMode_FullAccess_RequiresConfirmation()
    {
        await RunStaAsync(() =>
        {
            var panel = new SubmissionModePanel();
            panel.SetMode("auto");

            Assert.Equal("auto", panel.ReviewMode);
            Assert.True(panel.IsFullAccessWarningVisible);
            Assert.False(panel.IsGateSatisfied);

            // Check confirmation box
            panel.FullAccessConfirmed = true;
            Assert.True(panel.IsGateSatisfied);

            // Uncheck confirmation box
            panel.FullAccessConfirmed = false;
            Assert.False(panel.IsGateSatisfied);

            panel.Dispose();
            return Task.CompletedTask;
        });
    }

    [Fact]
    public async Task SubmissionMode_Notify_DoesNotRequireConfirmation()
    {
        await RunStaAsync(() =>
        {
            var panel = new SubmissionModePanel();
            panel.SetMode("notify");

            Assert.Equal("notify", panel.ReviewMode);
            Assert.False(panel.IsFullAccessWarningVisible);
            Assert.True(panel.IsGateSatisfied);

            panel.Dispose();
            return Task.CompletedTask;
        });
    }

    [Fact]
    public async Task SubmissionMode_SetModeWithConfirmedFlag_RestoresState()
    {
        await RunStaAsync(() =>
        {
            var panel = new SubmissionModePanel();
            panel.SetMode("auto", confirmed: true);

            Assert.Equal("auto", panel.ReviewMode);
            Assert.True(panel.FullAccessConfirmed);
            Assert.True(panel.IsGateSatisfied);

            panel.Dispose();
            return Task.CompletedTask;
        });
    }
}

