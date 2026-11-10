using System.Drawing;
using MagangLog.Desktop.Models;
using MagangLog.Desktop.Services;

namespace MagangLog.Desktop.Forms;

/// <summary>
/// Modal dialog displaying details of a past or selected day's logbook entry,
/// including official text (Aktivitas, Pembelajaran, Kendala), evidence references, and status.
/// </summary>
public class DayDetailForm : Form
{
    private readonly BackendApiClient? _apiClient;
    public string TargetDate { get; }

    public Label DateLabel { get; }
    public Label StatusBadgeLabel { get; }
    public Label KehadiranLabel { get; }
    public TextBox AktivitasTextBox { get; }
    public TextBox PembelajaranTextBox { get; }
    public TextBox KendalaTextBox { get; }
    public Label EvidenceSummaryLabel { get; }
    public Button CloseButton { get; }

    public DayDetailForm(
        string dateStr,
        EntryDetailResponse? entry = null,
        BackendApiClient? apiClient = null)
    {
        TargetDate = dateStr;
        _apiClient = apiClient;

        Text = $"Detail Logbook — {TargetDate}";
        StartPosition = FormStartPosition.CenterParent;
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = false;
        MinimizeBox = false;
        ShowInTaskbar = false;
        Size = new Size(680, 640);
        BackColor = Color.FromArgb(248, 250, 252);
        Padding = new Padding(20);

        // Header Panel
        var headerPanel = new Panel
        {
            Dock = DockStyle.Top,
            Height = 56,
            BackColor = Color.White,
            Padding = new Padding(16, 12, 16, 12),
            BorderStyle = BorderStyle.FixedSingle
        };

        DateLabel = new Label
        {
            Text = $"Tanggal: {TargetDate}",
            Font = new Font("Segoe UI", 12f, FontStyle.Bold),
            ForeColor = Color.FromArgb(15, 23, 42),
            Dock = DockStyle.Left,
            AutoSize = true,
            TextAlign = ContentAlignment.MiddleLeft
        };

        StatusBadgeLabel = new Label
        {
            Text = "⚪ KOSONG",
            Font = new Font("Segoe UI", 10f, FontStyle.Bold),
            Dock = DockStyle.Right,
            AutoSize = true,
            TextAlign = ContentAlignment.MiddleRight
        };

        headerPanel.Controls.Add(DateLabel);
        headerPanel.Controls.Add(StatusBadgeLabel);

        // Bottom Bar
        var bottomPanel = new Panel
        {
            Dock = DockStyle.Bottom,
            Height = 50,
            BackColor = Color.Transparent,
            Padding = new Padding(0, 10, 0, 0)
        };

        CloseButton = new Button
        {
            Text = "Tutup",
            Width = 110,
            Height = 36,
            Dock = DockStyle.Right,
            BackColor = Color.FromArgb(241, 245, 249),
            ForeColor = Color.FromArgb(30, 41, 59),
            FlatStyle = FlatStyle.Flat,
            Font = new Font("Segoe UI", 9.5f, FontStyle.Bold),
            Cursor = Cursors.Hand
        };
        CloseButton.FlatAppearance.BorderColor = Color.FromArgb(203, 213, 225);
        CloseButton.Click += (s, e) => CloseDialog();
        bottomPanel.Controls.Add(CloseButton);

        // Main Content Panel (Scrollable)
        var contentPanel = new Panel
        {
            Dock = DockStyle.Fill,
            AutoScroll = true,
            Padding = new Padding(0, 12, 0, 12)
        };

        var flow = new FlowLayoutPanel
        {
            Dock = DockStyle.Top,
            FlowDirection = FlowDirection.TopDown,
            AutoSize = true,
            AutoSizeMode = AutoSizeMode.GrowAndShrink,
            WrapContents = false,
            Width = 620
        };

        // Kehadiran row
        var pnlKehadiran = new Panel { Width = 610, Height = 32, Margin = new Padding(0, 0, 0, 8) };
        var lblKhdTitle = new Label
        {
            Text = "Status Kehadiran:",
            Font = new Font("Segoe UI", 9.5f, FontStyle.Bold),
            ForeColor = Color.FromArgb(71, 85, 105),
            Dock = DockStyle.Left,
            AutoSize = true
        };
        KehadiranLabel = new Label
        {
            Text = "Hadir",
            Font = new Font("Segoe UI", 9.5f, FontStyle.Regular),
            ForeColor = Color.FromArgb(15, 23, 42),
            Dock = DockStyle.Fill,
            Padding = new Padding(120, 0, 0, 0)
        };
        pnlKehadiran.Controls.Add(KehadiranLabel);
        pnlKehadiran.Controls.Add(lblKhdTitle);
        flow.Controls.Add(pnlKehadiran);

        // Aktivitas
        AktivitasTextBox = CreateReadOnlyTextBox();
        flow.Controls.Add(CreateFieldBox("Aktivitas Utama", AktivitasTextBox, 110));

        // Pembelajaran
        PembelajaranTextBox = CreateReadOnlyTextBox();
        flow.Controls.Add(CreateFieldBox("Pembelajaran / Refleksi", PembelajaranTextBox, 90));

        // Kendala
        KendalaTextBox = CreateReadOnlyTextBox();
        flow.Controls.Add(CreateFieldBox("Kendala & Hambatan", KendalaTextBox, 80));

        // Evidence summary
        var pnlEvidence = new Panel { Width = 610, Height = 36, Margin = new Padding(0, 4, 0, 0) };
        EvidenceSummaryLabel = new Label
        {
            Text = "Bukti Terkait: Tidak ada bukti aktivitas terekam.",
            Font = new Font("Segoe UI", 9f, FontStyle.Italic),
            ForeColor = Color.FromArgb(100, 116, 139),
            Dock = DockStyle.Fill
        };
        pnlEvidence.Controls.Add(EvidenceSummaryLabel);
        flow.Controls.Add(pnlEvidence);

        contentPanel.Controls.Add(flow);

        Controls.Add(contentPanel);
        Controls.Add(bottomPanel);
        Controls.Add(headerPanel);

        if (entry != null)
        {
            LoadEntry(entry);
        }
        else
        {
            SetEmptyState();
        }
    }

    private static TextBox CreateReadOnlyTextBox()
    {
        return new TextBox
        {
            Multiline = true,
            ReadOnly = true,
            Dock = DockStyle.Fill,
            ScrollBars = ScrollBars.Vertical,
            Font = new Font("Segoe UI", 9.5f, FontStyle.Regular),
            BackColor = Color.White,
            ForeColor = Color.FromArgb(15, 23, 42)
        };
    }

    private static GroupBox CreateFieldBox(string title, TextBox textBox, int height)
    {
        var gb = new GroupBox
        {
            Text = title,
            Width = 610,
            Height = height,
            Font = new Font("Segoe UI", 9f, FontStyle.Bold),
            ForeColor = Color.FromArgb(51, 65, 85),
            Margin = new Padding(0, 0, 0, 8),
            Padding = new Padding(10, 6, 10, 8)
        };
        gb.Controls.Add(textBox);
        return gb;
    }

    public void LoadEntry(EntryDetailResponse entry)
    {
        KehadiranLabel.Text = entry.Kehadiran ?? "Hadir";
        AktivitasTextBox.Text = entry.Aktivitas ?? string.Empty;
        PembelajaranTextBox.Text = entry.Pembelajaran ?? string.Empty;
        KendalaTextBox.Text = entry.Kendala ?? string.Empty;

        var status = entry.Status?.ToUpperInvariant() ?? "TERKIRIM";
        UpdateStatusBadge(status);

        if (entry.EvidenceRefs != null && entry.EvidenceRefs.Count > 0)
        {
            var summary = string.Join(", ", entry.EvidenceRefs.Select(kv => $"{kv.Key} ({kv.Value.Count})"));
            EvidenceSummaryLabel.Text = $"Bukti Terkait: {summary}";
            EvidenceSummaryLabel.Font = new Font("Segoe UI", 9f, FontStyle.Regular);
            EvidenceSummaryLabel.ForeColor = Color.FromArgb(30, 41, 59);
        }
    }

    private void SetEmptyState()
    {
        KehadiranLabel.Text = "-";
        AktivitasTextBox.Text = "Tidak ada draf atau catatan resmi logbook yang tersimpan untuk tanggal ini.";
        PembelajaranTextBox.Text = "-";
        KendalaTextBox.Text = "-";
        UpdateStatusBadge("KOSONG");
    }

    private void UpdateStatusBadge(string status)
    {
        StatusBadgeLabel.Text = status switch
        {
            "TERKIRIM" => "🟢 TERKIRIM",
            "BERHASIL" => "🟢 BERHASIL",
            "PENDING" => "🟡 PENDING",
            "LIBUR" => "⚪ LIBUR",
            "TERKUNCI" => "🔴 TERKUNCI",
            _ => "⚪ KOSONG"
        };
        StatusBadgeLabel.ForeColor = status switch
        {
            "TERKIRIM" or "BERHASIL" => Color.FromArgb(22, 101, 52),
            "PENDING" => Color.FromArgb(133, 77, 14),
            "TERKUNCI" => Color.FromArgb(153, 27, 27),
            _ => Color.FromArgb(71, 85, 105)
        };
    }

    public void CloseDialog()
    {
        Close();
    }
}
