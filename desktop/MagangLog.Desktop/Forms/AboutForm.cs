using System.Diagnostics;
using System.Drawing;

namespace MagangLog.Desktop.Forms;

/// <summary>
/// Modal dialog providing full attribution to creator and lead developer
/// VIO GUSTIAN NUR ALAMSYAH (@viogustian), along with system architecture details and project links.
/// </summary>
public class AboutForm : Form
{
    public const string GitHubProfileUrl = "https://github.com/viogustian";
    public const string RepositoryUrl = "https://github.com/viogustian/magang-log-portal";

    public Label AppTitleLabel { get; }
    public Label VersionLabel { get; }
    public Label SubtitleLabel { get; }

    public Label DeveloperNameLabel { get; }
    public Label DeveloperRoleLabel { get; }
    public Label DeveloperGitHubLabel { get; }
    public Label DedicationLabel { get; }

    public Label ArchitectureSpecsLabel { get; }
    public TextBox? ArchitectureTextBox => null;
    public string ArchitectureSpecsText => ArchitectureSpecsLabel.Text;

    public Button GitHubButton { get; }
    public Button RepoButton { get; }
    public Button CloseButton { get; }

    public Action<string> UrlOpener { get; set; } = url =>
    {
        try
        {
            Process.Start(new ProcessStartInfo
            {
                FileName = url,
                UseShellExecute = true
            });
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                $"Gagal membuka tautan peramban: {ex.Message}",
                "Kesalahan Peramban",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
        }
    };

    public AboutForm()
    {
        Text = "Tentang Pengembang & Arsitektur Sistem";
        StartPosition = FormStartPosition.CenterParent;
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = false;
        MinimizeBox = false;
        ShowInTaskbar = false;
        Size = new Size(680, 640);
        BackColor = Color.FromArgb(248, 250, 252);
        Padding = new Padding(24, 20, 24, 20);

        // Header Section (App Icon badge & Title)
        var headerPanel = new Panel
        {
            Dock = DockStyle.Top,
            Height = 90,
            BackColor = Color.White,
            Padding = new Padding(16, 12, 16, 12),
            BorderStyle = BorderStyle.FixedSingle
        };

        var logoBadge = new Panel
        {
            Width = 56,
            Height = 56,
            BackColor = Color.FromArgb(30, 58, 138), // Blue-900
            Dock = DockStyle.Left,
            Margin = new Padding(0, 0, 14, 0)
        };
        var lblLogo = new Label
        {
            Text = "ML",
            Font = new Font("Segoe UI", 13f, FontStyle.Bold),
            ForeColor = Color.White,
            Dock = DockStyle.Fill,
            TextAlign = ContentAlignment.MiddleCenter
        };
        logoBadge.Controls.Add(lblLogo);

        var titleContainer = new Panel
        {
            Dock = DockStyle.Fill,
            Padding = new Padding(12, 0, 0, 0)
        };

        AppTitleLabel = new Label
        {
            Text = "MagangLog Portal — Local Desktop Dashboard",
            Font = new Font("Segoe UI", 11.5f, FontStyle.Bold),
            ForeColor = Color.FromArgb(15, 23, 42),
            Dock = DockStyle.Top,
            Height = 24
        };

        VersionLabel = new Label
        {
            Text = "v2.0.0 (Build 2026.11)",
            Font = new Font("Segoe UI", 9f, FontStyle.Bold),
            ForeColor = Color.FromArgb(2, 132, 199), // Sky-600
            Dock = DockStyle.Top,
            Height = 20
        };

        SubtitleLabel = new Label
        {
            Text = "Sistem Pengisian Logbook Magang Otomatis, Andal & Aman",
            Font = new Font("Segoe UI", 8.5f, FontStyle.Italic),
            ForeColor = Color.FromArgb(100, 116, 139),
            Dock = DockStyle.Top,
            Height = 20
        };

        titleContainer.Controls.Add(SubtitleLabel);
        titleContainer.Controls.Add(VersionLabel);
        titleContainer.Controls.Add(AppTitleLabel);

        headerPanel.Controls.Add(titleContainer);
        headerPanel.Controls.Add(logoBadge);

        // Content Area (Flow)
        var contentPanel = new Panel
        {
            Dock = DockStyle.Fill,
            AutoScroll = true,
            Padding = new Padding(0, 12, 0, 8)
        };

        var mainFlow = new FlowLayoutPanel
        {
            Dock = DockStyle.Top,
            FlowDirection = FlowDirection.TopDown,
            AutoSize = true,
            AutoSizeMode = AutoSizeMode.GrowAndShrink,
            WrapContents = false,
            Width = 620
        };

        // 1. Developer Profile GroupBox
        var devGroup = new GroupBox
        {
            Text = "Profil Pengembang Utama & Kreator",
            Width = 615,
            Height = 180,
            Font = new Font("Segoe UI", 9.5f, FontStyle.Bold),
            ForeColor = Color.FromArgb(51, 65, 85),
            Margin = new Padding(0, 0, 0, 10),
            Padding = new Padding(14, 10, 14, 10)
        };

        DeveloperNameLabel = new Label
        {
            Text = "VIO GUSTIAN NUR ALAMSYAH",
            Font = new Font("Segoe UI", 11f, FontStyle.Bold),
            ForeColor = Color.FromArgb(15, 23, 42),
            Dock = DockStyle.Top,
            Height = 22
        };

        DeveloperRoleLabel = new Label
        {
            Text = "Lead Developer & Creator",
            Font = new Font("Segoe UI", 9.5f, FontStyle.Bold),
            ForeColor = Color.FromArgb(2, 132, 199),
            Dock = DockStyle.Top,
            Height = 20
        };

        DeveloperGitHubLabel = new Label
        {
            Text = "GitHub: @viogustian (https://github.com/viogustian)",
            Font = new Font("Segoe UI", 9f, FontStyle.Regular),
            ForeColor = Color.FromArgb(71, 85, 105),
            Dock = DockStyle.Top,
            Height = 20
        };

        DedicationLabel = new Label
        {
            Text = "Dirancang dan dikembangkan secara independen untuk mendisiplinkan pengisian logbook " +
                   "peserta program magang ke portal Monev Kemnaker RI (MagangHub) secara transparan, " +
                   "menjaga privasi data lokal mutlak, dan bebas dari kerumitan terminal.",
            Font = new Font("Segoe UI", 9f, FontStyle.Regular),
            ForeColor = Color.FromArgb(51, 65, 85),
            Dock = DockStyle.Fill
        };

        devGroup.Controls.Add(DedicationLabel);
        devGroup.Controls.Add(DeveloperGitHubLabel);
        devGroup.Controls.Add(DeveloperRoleLabel);
        devGroup.Controls.Add(DeveloperNameLabel);
        mainFlow.Controls.Add(devGroup);

        // 2. Architecture & Technical Specs GroupBox
        var archGroup = new GroupBox
        {
            Text = "Spesifikasi Teknis & Arsitektur Sistem",
            Width = 615,
            Height = 180,
            Font = new Font("Segoe UI", 9.5f, FontStyle.Bold),
            ForeColor = Color.FromArgb(51, 65, 85),
            Margin = new Padding(0, 0, 0, 8),
            Padding = new Padding(14, 10, 14, 10)
        };

        ArchitectureSpecsLabel = new Label
        {
            Dock = DockStyle.Fill,
            Font = new Font("Segoe UI", 9f, FontStyle.Regular),
            BackColor = Color.Transparent,
            ForeColor = Color.FromArgb(30, 41, 59),
            Text = "• Desktop UI: .NET 8 Windows Forms (C# High-DPI Native UI)\r\n" +
                   "• Backend Service: Python 3.12+ FastAPI (Loopback localhost API)\r\n" +
                   "• AI Drafting Engine: Google Gemini API via Google AI Studio Client\r\n" +
                   "• Otomasi Web: Playwright Chromium (Automasi Monev MagangHub Kemnaker)\r\n" +
                   "• Database & Ledger: SQLite Local Immutable Ledger (data/state.db)\r\n" +
                   "• Lisensi: MIT License — Hak Cipta © 2026 Vio Gustian Nur Alamsyah."
        };
        archGroup.Controls.Add(ArchitectureSpecsLabel);
        mainFlow.Controls.Add(archGroup);

        contentPanel.Controls.Add(mainFlow);

        // Bottom Action Bar
        var bottomPanel = new Panel
        {
            Dock = DockStyle.Bottom,
            Height = 46,
            BackColor = Color.Transparent,
            Padding = new Padding(0, 6, 0, 0)
        };

        GitHubButton = new Button
        {
            Text = "Kunjungi GitHub Pengembang 🌐",
            Height = 36,
            AutoSize = true,
            Padding = new Padding(12, 0, 12, 0),
            Dock = DockStyle.Left,
            BackColor = Color.FromArgb(241, 245, 249),
            ForeColor = Color.FromArgb(30, 41, 59),
            FlatStyle = FlatStyle.Flat,
            Font = new Font("Segoe UI", 9f, FontStyle.Regular),
            Cursor = Cursors.Hand
        };
        GitHubButton.FlatAppearance.BorderColor = Color.FromArgb(203, 213, 225);
        GitHubButton.Click += (s, e) => OpenGitHubProfile();

        RepoButton = new Button
        {
            Text = "Dokumentasi & Repositori 📖",
            Height = 36,
            AutoSize = true,
            Padding = new Padding(12, 0, 12, 0),
            Dock = DockStyle.Left,
            BackColor = Color.FromArgb(241, 245, 249),
            ForeColor = Color.FromArgb(30, 41, 59),
            FlatStyle = FlatStyle.Flat,
            Font = new Font("Segoe UI", 9f, FontStyle.Regular),
            Cursor = Cursors.Hand,
            Margin = new Padding(8, 0, 0, 0)
        };
        RepoButton.FlatAppearance.BorderColor = Color.FromArgb(203, 213, 225);
        RepoButton.Click += (s, e) => OpenRepository();

        CloseButton = new Button
        {
            Text = "Tutup",
            Width = 90,
            Height = 36,
            Dock = DockStyle.Right,
            BackColor = Color.FromArgb(226, 232, 240),
            ForeColor = Color.FromArgb(15, 23, 42),
            FlatStyle = FlatStyle.Flat,
            Font = new Font("Segoe UI", 9.5f, FontStyle.Bold),
            Cursor = Cursors.Hand
        };
        CloseButton.FlatAppearance.BorderColor = Color.FromArgb(203, 213, 225);
        CloseButton.Click += (s, e) => CloseDialog();

        bottomPanel.Controls.Add(RepoButton);
        bottomPanel.Controls.Add(GitHubButton);
        bottomPanel.Controls.Add(CloseButton);

        Controls.Add(contentPanel);
        Controls.Add(bottomPanel);
        Controls.Add(headerPanel);
    }

    public void OpenGitHubProfile()
    {
        UrlOpener?.Invoke(GitHubProfileUrl);
    }

    public void OpenRepository()
    {
        UrlOpener?.Invoke(RepositoryUrl);
    }

    public void CloseDialog()
    {
        Close();
    }
}
