using System.Net;
using MagangLog.Desktop.Controls;
using MagangLog.Desktop.Models;
using MagangLog.Desktop.Services;
using Xunit;

namespace MagangLog.Desktop.Tests;

public class FallbackNotePanelTests
{
    [Fact]
    public void TestFallbackNotePanelInitialization()
    {
        var panel = new FallbackNotePanel();

        Assert.NotNull(panel.CategoryComboBox);
        Assert.Equal(3, panel.CategoryComboBox.Items.Count);
        Assert.Equal("Aktivitas", panel.CategoryComboBox.SelectedItem);

        Assert.NotNull(panel.NoteTextBox);
        Assert.Empty(panel.NoteTextBox.Text);

        Assert.NotNull(panel.SendNoteButton);
        Assert.NotNull(panel.SwitchToEditorButton);
        Assert.False(panel.ErrorLabel.Visible);
    }

    [Theory]
    [InlineData("Aktivitas", "aktivitas")]
    [InlineData("Pembelajaran", "pembelajaran")]
    [InlineData("Kendala", "kendala")]
    public void TestCategoryKeyResolution(string displayCategory, string expectedKey)
    {
        var panel = new FallbackNotePanel();
        panel.CategoryComboBox.SelectedItem = displayCategory;

        var key = panel.GetSelectedCategoryKey();
        Assert.Equal(expectedKey, key);
    }

    [Fact]
    public async Task TestSubmitEmptyNote_ShowsValidationError()
    {
        var handler = new MockHttpMessageHandler("{}");
        var client = new BackendApiClient(new HttpClient(handler));
        var panel = new FallbackNotePanel(client);

        panel.NoteTextBox.Text = "   ";
        var submittedFired = false;
        panel.OnNoteSubmitted += () => submittedFired = true;

        var success = await panel.SubmitNoteAsync("2026-11-10");

        Assert.False(success);
        Assert.False(submittedFired);
        Assert.True(panel.ErrorLabel.Visible);
        Assert.Contains("Catatan tidak boleh kosong", panel.ErrorLabel.Text);
        Assert.Empty(handler.SentRequests);
    }

    [Fact]
    public async Task TestSubmitValidNote_Success_ClearsTextAndTriggersEvent()
    {
        var cannedJson = """
        {
            "success": true,
            "note_id": "note-created-1",
            "created_at": "2026-11-10T10:15:00Z"
        }
        """;
        var handler = new MockHttpMessageHandler(cannedJson);
        var client = new BackendApiClient(new HttpClient(handler));
        var panel = new FallbackNotePanel(client);

        panel.CategoryComboBox.SelectedItem = "Aktivitas";
        panel.NoteTextBox.Text = "Mengerjakan tugas integrasi FallbackNotePanel dengan unit testing.";

        var submittedFired = false;
        panel.OnNoteSubmitted += () => submittedFired = true;

        var success = await panel.SubmitNoteAsync("2026-11-10");

        Assert.True(success);
        Assert.True(submittedFired);
        Assert.Empty(panel.NoteTextBox.Text);
        Assert.False(panel.ErrorLabel.Visible);
        Assert.Single(handler.SentRequests);
        Assert.Equal(HttpMethod.Post, handler.SentRequests[0].Method);
        Assert.EndsWith("/api/notes", handler.SentRequests[0].RequestUri!.AbsolutePath);
    }

    [Fact]
    public void TestSwitchToEditorButton_FiresEvent()
    {
        var panel = new FallbackNotePanel();
        var switchedFired = false;
        panel.OnSwitchToEditorRequested += () => switchedFired = true;

        panel.SwitchToEditor();

        Assert.True(switchedFired);
    }
}
