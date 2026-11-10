using System.Drawing;
using MagangLog.Desktop.Controls;
using MagangLog.Desktop.Models;
using MagangLog.Desktop.Services;
using Xunit;

namespace MagangLog.Desktop.Tests;

public class DraftEditorPanelTests
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

    [Fact]
    public void TestDraftEditorPanelInitializesComponents()
    {
        RunSta(() =>
        {
            var handler = new MockHttpMessageHandler("{}");
            var client = new BackendApiClient(new HttpClient(handler));

            using var panel = new DraftEditorPanel(client);

            Assert.True(panel.AutoScroll);
            Assert.NotNull(panel.KehadiranComboBox);
            Assert.Equal(4, panel.KehadiranComboBox.Items.Count);
            Assert.Contains("Hadir", panel.KehadiranComboBox.Items.Cast<string>());
            Assert.Contains("Izin", panel.KehadiranComboBox.Items.Cast<string>());
            Assert.Contains("Sakit", panel.KehadiranComboBox.Items.Cast<string>());
            Assert.Contains("Cuti", panel.KehadiranComboBox.Items.Cast<string>());
            Assert.Equal("Hadir", panel.KehadiranComboBox.SelectedItem);

            Assert.NotNull(panel.AktivitasTextBox);
            Assert.NotNull(panel.PembelajaranTextBox);
            Assert.NotNull(panel.KendalaTextBox);
            Assert.True(panel.AktivitasTextBox.Multiline);
            Assert.Equal(ScrollBars.Vertical, panel.AktivitasTextBox.ScrollBars);

            Assert.Equal("(0/5000 karakter)", panel.AktivitasCharCountLabel.Text);
            Assert.Equal(Color.Red.ToArgb(), panel.AktivitasCharCountLabel.ForeColor.ToArgb());

            Assert.NotNull(panel.SaveDraftButton);
            Assert.NotNull(panel.RegenerateDraftButton);
            Assert.NotNull(panel.ApproveAndSubmitButton);
            Assert.False(panel.ApproveAndSubmitButton.Enabled);

            Assert.NotNull(panel.SubmissionProgressBar);
            Assert.NotNull(panel.ProgressStepLabel);
        });
    }

    [Fact]
    public void TestLiveCharacterCountingAndColorThresholds()
    {
        RunSta(() =>
        {
            var handler = new MockHttpMessageHandler("{}");
            var client = new BackendApiClient(new HttpClient(handler));

            using var panel = new DraftEditorPanel(client);

            // < 100 characters -> Red
            panel.AktivitasTextBox.Text = new string('A', 80);
            Assert.Equal("(80/5000 karakter)", panel.AktivitasCharCountLabel.Text);
            Assert.Equal(Color.Red.ToArgb(), panel.AktivitasCharCountLabel.ForeColor.ToArgb());

            // 100 - 4900 characters -> Green
            panel.AktivitasTextBox.Text = new string('B', 150);
            Assert.Equal("(150/5000 karakter)", panel.AktivitasCharCountLabel.Text);
            Assert.Equal(Color.Green.ToArgb(), panel.AktivitasCharCountLabel.ForeColor.ToArgb());

            // > 4900 characters -> OrangeRed
            panel.AktivitasTextBox.Text = new string('C', 4920);
            Assert.Equal("(4920/5000 karakter)", panel.AktivitasCharCountLabel.Text);
            Assert.Equal(Color.OrangeRed.ToArgb(), panel.AktivitasCharCountLabel.ForeColor.ToArgb());
        });
    }

    [Fact]
    public void TestApproveAndSubmitButtonEnablesOnlyWhenAllThreeFieldsMeetMinimum()
    {
        RunSta(() =>
        {
            var handler = new MockHttpMessageHandler("{}");
            var client = new BackendApiClient(new HttpClient(handler));

            using var panel = new DraftEditorPanel(client);

            var validText = new string('X', 120);
            var shortText = new string('Y', 80);

            panel.AktivitasTextBox.Text = validText;
            panel.PembelajaranTextBox.Text = shortText;
            panel.KendalaTextBox.Text = validText;
            Assert.False(panel.ApproveAndSubmitButton.Enabled);

            panel.PembelajaranTextBox.Text = validText;
            Assert.True(panel.ApproveAndSubmitButton.Enabled);

            panel.KendalaTextBox.Text = shortText;
            Assert.False(panel.ApproveAndSubmitButton.Enabled);
        });
    }

    [Fact]
    public void TestLoadEntryPopulatesFieldsAndCalculatesCounters()
    {
        RunSta(() =>
        {
            var handler = new MockHttpMessageHandler("{}");
            var client = new BackendApiClient(new HttpClient(handler));

            using var panel = new DraftEditorPanel(client);

            var entry = new EntryDetailResponse
            {
                EntryId = "entry-1",
                WorkDate = "2026-11-10",
                Kehadiran = "Izin",
                Aktivitas = new string('A', 110),
                Pembelajaran = new string('B', 120),
                Kendala = new string('C', 130),
                Status = "DRAFTED"
            };

            panel.LoadEntry(entry);

            Assert.Equal("Izin", panel.KehadiranComboBox.SelectedItem);
            Assert.Equal(entry.Aktivitas, panel.AktivitasTextBox.Text);
            Assert.Equal(entry.Pembelajaran, panel.PembelajaranTextBox.Text);
            Assert.Equal(entry.Kendala, panel.KendalaTextBox.Text);

            Assert.Equal("(110/5000 karakter)", panel.AktivitasCharCountLabel.Text);
            Assert.Equal("(120/5000 karakter)", panel.PembelajaranCharCountLabel.Text);
            Assert.Equal("(130/5000 karakter)", panel.KendalaCharCountLabel.Text);
            Assert.True(panel.ApproveAndSubmitButton.Enabled);
        });
    }

    [Fact]
    public async Task TestSaveDraftAsyncCallsApi()
    {
        var editJson = """
        {
            "success": true,
            "validation_passed": true,
            "validation_errors": []
        }
        """;

        var handler = new MockHttpMessageHandler(editJson);
        var client = new BackendApiClient(new HttpClient(handler));

        DraftEditorPanel? panel = null;
        RunSta(() =>
        {
            panel = new DraftEditorPanel(client);
            panel.AktivitasTextBox.Text = new string('A', 120);
            panel.PembelajaranTextBox.Text = new string('B', 120);
            panel.KendalaTextBox.Text = new string('C', 120);
        });

        try
        {
            var success = await panel!.SaveDraftAsync();
            Assert.True(success);
            Assert.Single(handler.SentRequests);
            Assert.EndsWith("/api/entry/edit", handler.SentRequests[0].RequestUri!.AbsolutePath);
        }
        finally
        {
            panel?.Dispose();
        }
    }

    [Fact]
    public async Task TestRegenerateDraftAsyncCallsApiAndLoadsResult()
    {
        var draftJson = """
        {
            "success": true,
            "draft": {
                "entry_id": "regen-1",
                "work_date": "2026-11-10",
                "kehadiran": "Hadir",
                "aktivitas": "Regenerated aktivitas content here with sufficient length to be valid",
                "pembelajaran": "Regenerated pembelajaran content here with sufficient length to be valid",
                "kendala": "Regenerated kendala content here with sufficient length to be valid",
                "status": "DRAFTED",
                "validation_passed": true,
                "validation_errors": []
            },
            "validation_passed": true,
            "validation_errors": []
        }
        """;

        var handler = new MockHttpMessageHandler(draftJson);
        var client = new BackendApiClient(new HttpClient(handler));

        DraftEditorPanel? panel = null;
        RunSta(() =>
        {
            panel = new DraftEditorPanel(client);
        });

        try
        {
            var success = await panel!.RegenerateDraftAsync("2026-11-10");
            Assert.True(success);
            Assert.Equal("Regenerated aktivitas content here with sufficient length to be valid", panel.AktivitasTextBox.Text);
        }
        finally
        {
            panel?.Dispose();
        }
    }

    [Fact]
    public async Task TestApproveAndSubmitAsyncUpdatesProgressStages()
    {
        var approveJson = """
        {
            "success": true,
            "final_status": "SUDAH_TERKIRIM",
            "error_message": null
        }
        """;

        var handler = new MockHttpMessageHandler(approveJson);
        var client = new BackendApiClient(new HttpClient(handler));

        DraftEditorPanel? panel = null;
        RunSta(() =>
        {
            panel = new DraftEditorPanel(client);
            panel.AktivitasTextBox.Text = new string('A', 120);
            panel.PembelajaranTextBox.Text = new string('B', 120);
            panel.KendalaTextBox.Text = new string('C', 120);
        });

        try
        {
            var success = await panel!.ApproveAndSubmitAsync("2026-11-10");
            Assert.True(success);
            Assert.Equal(100, panel.SubmissionProgressBar.Value);
            Assert.Contains("Memverifikasi Halaman", panel.ProgressStepLabel.Text);
        }
        finally
        {
            panel?.Dispose();
        }
    }
}
