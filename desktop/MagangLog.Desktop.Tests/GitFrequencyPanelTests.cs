using System.Threading;
using MagangLog.Desktop.Controls;
using MagangLog.Desktop.Models;
using Xunit;

namespace MagangLog.Desktop.Tests;

public class GitFrequencyPanelTests
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
    public async Task GitFrequency_Sering_SetsExpectedFlags()
    {
        await RunStaAsync(() =>
        {
            var panel = new GitFrequencyPanel();
            panel.SetFrequency("sering");

            var config = panel.GetConfig();
            Assert.Equal("sering", config.GitFrequency);
            Assert.True(config.GitEnabled);
            Assert.True(config.AppEnabled);
            Assert.False(config.BrowserEnabled);
            Assert.False(panel.IsBrowserConsentVisible);

            panel.Dispose();
            return Task.CompletedTask;
        });
    }

    [Fact]
    public async Task GitFrequency_Jarang_SetsExpectedFlags()
    {
        await RunStaAsync(() =>
        {
            var panel = new GitFrequencyPanel();
            panel.SetFrequency("jarang");

            var config = panel.GetConfig();
            Assert.Equal("jarang", config.GitFrequency);
            Assert.True(config.GitEnabled);
            Assert.True(config.AppEnabled);
            Assert.True(config.BrowserEnabled);
            Assert.True(panel.IsBrowserConsentVisible);

            panel.Dispose();
            return Task.CompletedTask;
        });
    }

    [Fact]
    public async Task GitFrequency_TidakSamaSekali_SetsExpectedFlags()
    {
        await RunStaAsync(() =>
        {
            var panel = new GitFrequencyPanel();
            panel.SetFrequency("tidak_sama_sekali");

            var config = panel.GetConfig();
            Assert.Equal("tidak_sama_sekali", config.GitFrequency);
            Assert.False(config.GitEnabled);
            Assert.True(config.AppEnabled);
            Assert.True(config.BrowserEnabled);
            Assert.True(panel.IsBrowserConsentVisible);

            panel.Dispose();
            return Task.CompletedTask;
        });
    }

    [Fact]
    public async Task UncheckingConsent_OverridesEnabledFlagToFalse()
    {
        await RunStaAsync(() =>
        {
            var panel = new GitFrequencyPanel();
            panel.SetFrequency("jarang");

            // Uncheck browser consent
            panel.BrowserConsent = false;
            var config1 = panel.GetConfig();
            Assert.True(config1.GitEnabled);
            Assert.True(config1.AppEnabled);
            Assert.False(config1.BrowserEnabled);

            // Uncheck app consent
            panel.AppConsent = false;
            var config2 = panel.GetConfig();
            Assert.True(config2.GitEnabled);
            Assert.False(config2.AppEnabled);
            Assert.False(config2.BrowserEnabled);

            panel.Dispose();
            return Task.CompletedTask;
        });
    }

    [Fact]
    public async Task SetConfig_RestoresStateProperly()
    {
        await RunStaAsync(() =>
        {
            var panel = new GitFrequencyPanel();
            var saved = new SourcesConfig
            {
                GitFrequency = "tidak_sama_sekali",
                GitEnabled = false,
                AppEnabled = true,
                BrowserEnabled = false,
                AppConsent = true,
                BrowserConsent = false
            };

            panel.SetConfig(saved);

            var result = panel.GetConfig();
            Assert.Equal("tidak_sama_sekali", result.GitFrequency);
            Assert.False(result.GitEnabled);
            Assert.True(result.AppEnabled);
            Assert.False(result.BrowserEnabled);
            Assert.False(result.BrowserConsent);
            Assert.True(result.AppConsent);

            panel.Dispose();
            return Task.CompletedTask;
        });
    }
}

