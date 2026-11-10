using System.Threading;
using MagangLog.Desktop.Controls;
using Xunit;

namespace MagangLog.Desktop.Tests;

public class KeywordListPanelTests
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
    public async Task SetProfile_PopulatesProfileNameAndKeywords()
    {
        await RunStaAsync(() =>
        {
            var panel = new KeywordListPanel();
            panel.SetProfile("Software Engineer", new[] { "Code.exe", "git.exe", "Visual Studio Code" });

            Assert.Equal("Software Engineer", panel.ProfileName);
            Assert.Equal(3, panel.Keywords.Count);
            Assert.Contains("Code.exe", panel.Keywords);
            Assert.Contains("git.exe", panel.Keywords);
            Assert.Contains("Visual Studio Code", panel.Keywords);

            panel.Dispose();
            return Task.CompletedTask;
        });
    }

    [Fact]
    public async Task AddKeyword_AddsItemAndFiresKeywordsChanged()
    {
        await RunStaAsync(() =>
        {
            var panel = new KeywordListPanel();
            bool eventFired = false;
            panel.KeywordsChanged += (_, _) => eventFired = true;

            panel.AddKeyword("Figma.exe");

            Assert.Single(panel.Keywords);
            Assert.Equal("Figma.exe", panel.Keywords[0]);
            Assert.True(eventFired);

            panel.Dispose();
            return Task.CompletedTask;
        });
    }

    [Fact]
    public async Task RemoveKeyword_RemovesItemAndFiresKeywordsChanged()
    {
        await RunStaAsync(() =>
        {
            var panel = new KeywordListPanel();
            panel.SetProfile("UI/UX Designer", new[] { "Figma.exe", "XD.exe" });

            bool eventFired = false;
            panel.KeywordsChanged += (_, _) => eventFired = true;

            panel.RemoveKeyword("XD.exe");

            Assert.Single(panel.Keywords);
            Assert.Equal("Figma.exe", panel.Keywords[0]);
            Assert.True(eventFired);

            panel.Dispose();
            return Task.CompletedTask;
        });
    }

    [Fact]
    public async Task UpdateKeyword_ModifiesItemInlineAndFiresKeywordsChanged()
    {
        await RunStaAsync(() =>
        {
            var panel = new KeywordListPanel();
            panel.SetProfile("Developer", new[] { "Code.exe" });

            bool eventFired = false;
            panel.KeywordsChanged += (_, _) => eventFired = true;

            panel.UpdateKeyword(0, "Code-OSS.exe");

            Assert.Single(panel.Keywords);
            Assert.Equal("Code-OSS.exe", panel.Keywords[0]);
            Assert.True(eventFired);

            panel.Dispose();
            return Task.CompletedTask;
        });
    }
}

