using MagangLog.Desktop.Forms;
using MagangLog.Desktop.Models;
using MagangLog.Desktop.Services;
using Xunit;

namespace MagangLog.Desktop.Tests;

public class DayDetailFormTests
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
    public void TestDayDetailForm_InitializesWithEntryData()
    {
        RunSta(() =>
        {
            var entry = new EntryDetailResponse
            {
                EntryId = "entry-2026-10-21",
                WorkDate = "2026-10-21",
                Kehadiran = "Hadir",
                Aktivitas = "Mengembangkan fitur kalender bulanan dan dialog detail.",
                Pembelajaran = "Mempelajari integrasi DataGridView dengan custom cell formatting.",
                Kendala = "Tidak ada kendala yang menghambat.",
                Status = "TERKIRIM",
                ValidationPassed = true
            };

            using var form = new DayDetailForm("2026-10-21", entry);

            Assert.Contains("2026-10-21", form.DateLabel.Text);
            Assert.Contains("TERKIRIM", form.StatusBadgeLabel.Text);
            Assert.Equal("Hadir", form.KehadiranLabel.Text);
            Assert.Equal(entry.Aktivitas, form.AktivitasTextBox.Text);
            Assert.Equal(entry.Pembelajaran, form.PembelajaranTextBox.Text);
            Assert.Equal(entry.Kendala, form.KendalaTextBox.Text);
            Assert.NotNull(form.CloseButton);
        });
    }

    [Fact]
    public void TestDayDetailForm_WithoutEntry_ShowsNoData()
    {
        RunSta(() =>
        {
            using var form = new DayDetailForm("2026-10-22", null);

            Assert.Contains("2026-10-22", form.DateLabel.Text);
            Assert.Contains("KOSONG", form.StatusBadgeLabel.Text);
            Assert.Contains("Tidak ada draf atau catatan", form.AktivitasTextBox.Text);
        });
    }

    [Fact]
    public void TestDayDetailForm_CloseDialogMethod()
    {
        RunSta(() =>
        {
            using var form = new DayDetailForm("2026-10-21", null);
            _ = form.Handle; // Ensure window handle is created so FormClosed fires
            var closed = false;
            form.FormClosed += (s, e) => closed = true;

            form.CloseDialog();

            Assert.True(closed);
        });
    }
}
