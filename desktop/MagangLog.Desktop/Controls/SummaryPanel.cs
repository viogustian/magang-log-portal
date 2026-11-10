using System.Drawing;
using System.Windows.Forms;
using MagangLog.Desktop.Models;

namespace MagangLog.Desktop.Controls;

/// <summary>
/// Panel for Step 6 of the onboarding wizard displaying a consolidated, organized summary
/// of all configuration choices with quick "Ubah" buttons to jump back and revise specific inputs.
/// </summary>
public class SummaryPanel : Panel
{
    private readonly Label _lblRequirements;
    private readonly Label _lblFolders;
    private readonly Label _lblRole;
    private readonly Label _lblSources;
    private readonly Label _lblSubmission;

    public string FoldersSummaryText => _lblFolders.Text;
    public string RoleSummaryText => _lblRole.Text;
    public string SourcesSummaryText => _lblSources.Text;
    public string SubmissionSummaryText => _lblSubmission.Text;

    public event EventHandler<int>? EditSectionRequested;

    public SummaryPanel()
    {
        Dock = DockStyle.Fill;
        BackColor = Color.White;
        Padding = new Padding(8);
        AutoScroll = true;

        var mainContainer = new FlowLayoutPanel
        {
            Dock = DockStyle.Top,
            AutoSize = true,
            FlowDirection = FlowDirection.TopDown,
            WrapContents = false,
            Padding = new Padding(4)
        };

        // 1. System Requirements Card (No "Ubah" needed as Step 0 is the prerequisite gate)
        var cardReq = CreateSummaryCard("1. Requirement Sistem", out _lblRequirements, null);
        _lblRequirements.Text = "✅ Semua dependensi runtime utama terpenuhi (Python, Playwright, .NET SDK, Git).";

        // 2. Project Folders Card
        var cardFolders = CreateSummaryCard("2. Folder Proyek Dipantau", out _lblFolders, 1);

        // 3. Job Role & Keywords Card
        var cardRole = CreateSummaryCard("3. Peran Pekerjaan & Kata Kunci Deteksi", out _lblRole, 2);

        // 4. Git Frequency & Evidence Sources Card
        var cardSources = CreateSummaryCard("4. Frekuensi Git & Sumber Data Bukti", out _lblSources, 3);

        // 5. Submission Mode Card
        var cardSubmission = CreateSummaryCard("5. Mode Pengiriman Logbook ke Portal", out _lblSubmission, 4);

        mainContainer.Controls.Add(cardReq);
        mainContainer.Controls.Add(cardFolders);
        mainContainer.Controls.Add(cardRole);
        mainContainer.Controls.Add(cardSources);
        mainContainer.Controls.Add(cardSubmission);

        Controls.Add(mainContainer);
    }

    private Panel CreateSummaryCard(string title, out Label contentLabel, int? targetStepIndex)
    {
        var card = new Panel
        {
            Size = new Size(680, 68),
            BackColor = Color.FromArgb(248, 250, 252),
            BorderStyle = BorderStyle.FixedSingle,
            Margin = new Padding(0, 0, 0, 8),
            Padding = new Padding(12, 8, 12, 8)
        };

        var topRow = new Panel
        {
            Dock = DockStyle.Top,
            Height = 22
        };

        var lblTitle = new Label
        {
            Text = title,
            Dock = DockStyle.Left,
            AutoSize = true,
            Font = new Font(Font.FontFamily, 9f, FontStyle.Bold),
            ForeColor = Color.FromArgb(15, 23, 42)
        };
        topRow.Controls.Add(lblTitle);

        if (targetStepIndex.HasValue)
        {
            var btnEdit = new Button
            {
                Text = "✏️ Ubah",
                Dock = DockStyle.Right,
                Width = 75,
                Height = 22,
                BackColor = Color.White,
                ForeColor = Color.FromArgb(37, 99, 235),
                FlatStyle = FlatStyle.Flat,
                Font = new Font(Font.FontFamily, 8f, FontStyle.Bold),
                Cursor = Cursors.Hand
            };
            btnEdit.FlatAppearance.BorderColor = Color.FromArgb(191, 219, 254);
            var step = targetStepIndex.Value;
            btnEdit.Click += (_, _) => TriggerEditSection(step);
            topRow.Controls.Add(btnEdit);
        }

        contentLabel = new Label
        {
            Dock = DockStyle.Fill,
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Regular),
            ForeColor = Color.FromArgb(71, 85, 105),
            TextAlign = ContentAlignment.MiddleLeft
        };

        card.Controls.Add(contentLabel);
        card.Controls.Add(topRow);
        return card;
    }

    /// <summary>
    /// Invokes the EditSectionRequested event for a given step.
    /// </summary>
    public void TriggerEditSection(int targetStepIndex)
    {
        EditSectionRequested?.Invoke(this, targetStepIndex);
    }

    /// <summary>
    /// Refreshes card descriptions based on the consolidated WizardProgressState.
    /// </summary>
    public void RefreshSummary(WizardProgressState state)
    {
        if (state == null) return;

        // Folders
        if (state.ProjectFolders != null && state.ProjectFolders.Count > 0)
        {
            var folderList = string.Join("; ", state.ProjectFolders);
            _lblFolders.Text = $"📁 {state.ProjectFolders.Count} folder terdaftar: {folderList}";
        }
        else
        {
            _lblFolders.Text = "Belum ada folder proyek terdaftar.";
        }

        // Role & Keywords
        var roleName = string.IsNullOrWhiteSpace(state.ProfileName) ? "Belum ditentukan" : state.ProfileName;
        var kwList = (state.Keywords != null && state.Keywords.Count > 0)
            ? string.Join(", ", state.Keywords)
            : "Tidak ada kata kunci";
        _lblRole.Text = $"💼 Profil: {roleName}  |  Kata Kunci: {kwList}";

        // Sources
        if (state.Sources != null)
        {
            var freq = state.Sources.GitFrequency switch
            {
                "tidak_sama_sekali" => "Tidak sama sekali",
                "jarang" => "Jarang",
                _ => "Sering"
            };
            var git = state.Sources.GitEnabled ? "Git [Aktif]" : "Git [Nonaktif]";
            var app = state.Sources.AppEnabled ? "Aplikasi [Aktif]" : "Aplikasi [Nonaktif]";
            var browser = state.Sources.BrowserEnabled ? "Browser [Aktif]" : "Browser [Nonaktif]";
            _lblSources.Text = $"📊 Penggunaan Git: {freq}  |  {git}, {app}, {browser}";
        }
        else
        {
            _lblSources.Text = "Konfigurasi sumber data belum diatur.";
        }

        // Submission Mode
        var modeDesc = state.ReviewMode switch
        {
            "auto" => "Full Access — Draf AI otomatis diserahkan ke portal",
            "notify" => "Notifikasi Saja — Draf dibuat lokal tanpa kirim otomatis",
            _ => "Review Dulu (Direkomendasikan) — Perlu persetujuan di dashboard"
        };
        _lblSubmission.Text = $"🚀 Mode: {modeDesc}";
    }
}
