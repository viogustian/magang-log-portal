using System.Drawing;
using System.Windows.Forms;
using MagangLog.Desktop.Models;

namespace MagangLog.Desktop.Controls;

/// <summary>
/// Panel for Step 4 of the onboarding wizard allowing interns to select their Git usage
/// frequency, view active data sources mapping, and provide explicit privacy consents.
/// </summary>
public class GitFrequencyPanel : Panel
{
    private readonly RadioButton _rdoSering;
    private readonly RadioButton _rdoJarang;
    private readonly RadioButton _rdoTidakSamaSekali;

    private readonly Panel _pnlBrowserConsent;
    private readonly CheckBox _chkAppConsent;
    private readonly CheckBox _chkBrowserConsent;
    private readonly Label _lblSourceSummary;

    public event EventHandler? SourcesChanged;

    public string GitFrequency
    {
        get
        {
            if (_rdoTidakSamaSekali.Checked) return "tidak_sama_sekali";
            if (_rdoJarang.Checked) return "jarang";
            return "sering";
        }
        set => SetFrequency(value);
    }

    public bool GitEnabled => GitFrequency != "tidak_sama_sekali";

    public bool AppConsent
    {
        get => _chkAppConsent.Checked;
        set
        {
            _chkAppConsent.Checked = value;
            UpdateSummary();
        }
    }

    public bool BrowserConsent
    {
        get => _chkBrowserConsent.Checked;
        set
        {
            _chkBrowserConsent.Checked = value;
            UpdateSummary();
        }
    }

    public bool AppEnabled => AppConsent;

    public bool BrowserEnabled =>
        (GitFrequency == "jarang" || GitFrequency == "tidak_sama_sekali") && BrowserConsent;

    public bool IsBrowserConsentVisible => _pnlBrowserConsent.Visible;

    public bool HasActiveSources => GitEnabled || AppEnabled || BrowserEnabled;

    public GitFrequencyPanel()
    {
        Dock = DockStyle.Fill;
        BackColor = Color.White;
        Padding = new Padding(8);
        AutoScroll = true;

        // Top prompt label
        var lblTitle = new Label
        {
            Text = "Seberapa sering Anda menggunakan Git dalam pekerjaan magang?",
            Dock = DockStyle.Top,
            Height = 24,
            Font = new Font(Font.FontFamily, 9.5f, FontStyle.Bold),
            ForeColor = Color.FromArgb(30, 41, 59)
        };

        // Radio options container
        var optionsPanel = new Panel
        {
            Dock = DockStyle.Top,
            Height = 175,
            Padding = new Padding(4, 4, 4, 8)
        };

        var seringCard = CreateOptionCard(
            out _rdoSering,
            "Sering — hampir tiap hari push/commit",
            "Git menjadi sumber bukti utama. Aktivitas aplikasi aktif. Riwayat browser dinonaktifkan.",
            0);
        _rdoSering.Checked = true;
        _rdoSering.CheckedChanged += (_, _) => HandleFrequencyChanged();

        var jarangCard = CreateOptionCard(
            out _rdoJarang,
            "Jarang — sesekali saja",
            "Kombinasi commit Git, aktivitas aplikasi desktop, dan riwayat peramban pada domain kerja yang diizinkan.",
            56);
        _rdoJarang.CheckedChanged += (_, _) => HandleFrequencyChanged();

        var tidakCard = CreateOptionCard(
            out _rdoTidakSamaSekali,
            "Tidak sama sekali",
            "Fokus pada aktivitas aplikasi desktop dan riwayat peramban pada domain kerja yang diizinkan. Git dinonaktifkan.",
            112);
        _rdoTidakSamaSekali.CheckedChanged += (_, _) => HandleFrequencyChanged();

        optionsPanel.Controls.Add(tidakCard);
        optionsPanel.Controls.Add(jarangCard);
        optionsPanel.Controls.Add(seringCard);

        // --- Privacy Consent Section ---
        var consentGroup = new GroupBox
        {
            Text = "Persetujuan Privasi & Keamanan Data Lokal",
            Dock = DockStyle.Top,
            Height = 180,
            Font = new Font(Font.FontFamily, 9f, FontStyle.Bold),
            ForeColor = Color.FromArgb(30, 41, 59),
            Padding = new Padding(12, 10, 12, 10)
        };

        var lblPrivacyNotice = new Label
        {
            Text = "🔒 Semua bukti diproses 100% lokal di komputer ini. Tidak ada file dokumen yang dikirim ke server.",
            Dock = DockStyle.Top,
            Height = 22,
            Font = new Font(Font.FontFamily, 8f, FontStyle.Italic),
            ForeColor = Color.FromArgb(71, 85, 105)
        };

        // App activity consent card
        var pnlAppConsent = new Panel
        {
            Dock = DockStyle.Top,
            Height = 48,
            Padding = new Padding(0, 4, 0, 4)
        };

        _chkAppConsent = new CheckBox
        {
            Text = "Saya menyetujui pemantauan aktivitas aplikasi desktop & file baru dibuka (Windows Recent)",
            Dock = DockStyle.Top,
            Height = 22,
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Bold),
            ForeColor = Color.FromArgb(15, 23, 42),
            Checked = true
        };
        _chkAppConsent.CheckedChanged += (_, _) =>
        {
            UpdateSummary();
            SourcesChanged?.Invoke(this, EventArgs.Empty);
        };

        var lblAppDetail = new Label
        {
            Text = "Mendeteksi proses aplikasi aktif dan file terkait kata kunci profil kerja Anda.",
            Dock = DockStyle.Top,
            Height = 18,
            Font = new Font(Font.FontFamily, 8f, FontStyle.Regular),
            ForeColor = Color.FromArgb(100, 116, 139),
            Padding = new Padding(22, 0, 0, 0)
        };
        pnlAppConsent.Controls.Add(lblAppDetail);
        pnlAppConsent.Controls.Add(_chkAppConsent);

        // Browser history consent card
        _pnlBrowserConsent = new Panel
        {
            Dock = DockStyle.Top,
            Height = 52,
            Padding = new Padding(0, 4, 0, 4),
            Visible = false // only visible for 'jarang' or 'tidak_sama_sekali'
        };

        _chkBrowserConsent = new CheckBox
        {
            Text = "Saya menyetujui pembacaan riwayat peramban web lokal untuk domain kerja yang diizinkan",
            Dock = DockStyle.Top,
            Height = 22,
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Bold),
            ForeColor = Color.FromArgb(15, 23, 42),
            Checked = true
        };
        _chkBrowserConsent.CheckedChanged += (_, _) =>
        {
            UpdateSummary();
            SourcesChanged?.Invoke(this, EventArgs.Empty);
        };

        var lblBrowserDetail = new Label
        {
            Text = "Hanya memeriksa judul tab dan domain kerja (GitHub, StackOverflow, Figma, dll). Riwayat personal diabaikan.",
            Dock = DockStyle.Top,
            Height = 22,
            Font = new Font(Font.FontFamily, 8f, FontStyle.Regular),
            ForeColor = Color.FromArgb(100, 116, 139),
            Padding = new Padding(22, 0, 0, 0)
        };
        _pnlBrowserConsent.Controls.Add(lblBrowserDetail);
        _pnlBrowserConsent.Controls.Add(_chkBrowserConsent);

        consentGroup.Controls.Add(_pnlBrowserConsent);
        consentGroup.Controls.Add(pnlAppConsent);
        consentGroup.Controls.Add(lblPrivacyNotice);

        // Active sources summary badge
        var summaryPanel = new Panel
        {
            Dock = DockStyle.Top,
            Height = 36,
            Padding = new Padding(0, 8, 0, 0)
        };

        _lblSourceSummary = new Label
        {
            Dock = DockStyle.Fill,
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Bold),
            ForeColor = Color.FromArgb(22, 101, 52),
            TextAlign = ContentAlignment.MiddleLeft
        };
        summaryPanel.Controls.Add(_lblSourceSummary);

        // Assemble controls (Dock order)
        Controls.Add(summaryPanel);
        Controls.Add(consentGroup);
        Controls.Add(optionsPanel);
        Controls.Add(lblTitle);

        UpdateSummary();
    }

    private Panel CreateOptionCard(out RadioButton rdo, string title, string description, int topOffset)
    {
        var panel = new Panel
        {
            Location = new Point(4, topOffset),
            Size = new Size(680, 50),
            BackColor = Color.FromArgb(248, 250, 252),
            BorderStyle = BorderStyle.FixedSingle,
            Padding = new Padding(8, 4, 8, 4)
        };

        rdo = new RadioButton
        {
            Text = title,
            Dock = DockStyle.Top,
            Height = 22,
            Font = new Font(Font.FontFamily, 9f, FontStyle.Bold),
            ForeColor = Color.FromArgb(15, 23, 42)
        };

        var lblDesc = new Label
        {
            Text = description,
            Dock = DockStyle.Top,
            Height = 20,
            Font = new Font(Font.FontFamily, 8f, FontStyle.Regular),
            ForeColor = Color.FromArgb(100, 116, 139),
            Padding = new Padding(22, 0, 0, 0)
        };

        panel.Controls.Add(lblDesc);
        panel.Controls.Add(rdo);
        return panel;
    }

    public void SetFrequency(string frequency)
    {
        var clean = frequency?.Trim().ToLowerInvariant();
        if (clean == "tidak_sama_sekali")
        {
            _rdoTidakSamaSekali.Checked = true;
        }
        else if (clean == "jarang")
        {
            _rdoJarang.Checked = true;
        }
        else
        {
            _rdoSering.Checked = true;
        }
        HandleFrequencyChanged();
    }

    private void HandleFrequencyChanged()
    {
        var freq = GitFrequency;
        if (freq == "sering")
        {
            _pnlBrowserConsent.Visible = false;
        }
        else
        {
            _pnlBrowserConsent.Visible = true;
        }

        UpdateSummary();
        SourcesChanged?.Invoke(this, EventArgs.Empty);
    }

    private void UpdateSummary()
    {
        var gitStatus = GitEnabled ? "✅ Aktif" : "❌ Nonaktif";
        var appStatus = AppEnabled ? "✅ Aktif" : "❌ Nonaktif";
        var browserStatus = BrowserEnabled ? "✅ Aktif" : "❌ Nonaktif";

        _lblSourceSummary.Text = $"📊 Sumber Bukti Aktif: Git [{gitStatus}]  |  Aplikasi [{appStatus}]  |  Browser [{browserStatus}]";

        if (!HasActiveSources)
        {
            _lblSourceSummary.ForeColor = Color.FromArgb(220, 38, 38);
        }
        else
        {
            _lblSourceSummary.ForeColor = Color.FromArgb(22, 101, 52);
        }
    }

    /// <summary>
    /// Produces a snapshot of current sources configuration.
    /// </summary>
    public SourcesConfig GetConfig()
    {
        return new SourcesConfig
        {
            GitFrequency = GitFrequency,
            GitEnabled = GitEnabled,
            AppEnabled = AppEnabled,
            BrowserEnabled = BrowserEnabled,
            AppConsent = AppConsent,
            BrowserConsent = BrowserConsent
        };
    }

    /// <summary>
    /// Rehydrates state from a saved SourcesConfig.
    /// </summary>
    public void SetConfig(SourcesConfig config)
    {
        if (config == null) return;

        SetFrequency(config.GitFrequency);
        _chkAppConsent.Checked = config.AppConsent;
        _chkBrowserConsent.Checked = config.BrowserConsent;
        UpdateSummary();
    }
}
