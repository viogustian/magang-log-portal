using System.Drawing;
using System.Windows.Forms;
using MagangLog.Desktop.Controls;
using MagangLog.Desktop.Models;
using MagangLog.Desktop.Services;

namespace MagangLog.Desktop.Forms;

/// <summary>
/// Comprehensive settings reconfiguration dialog providing tabbed management of:
/// Tab 1: WorkProfile & Application Detection Keywords
/// Tab 2: Project Work Folders & Git Repositories
/// Tab 3: Data Sources, Git Intensity & Browser Privacy Allowlist
/// Tab 4: Daily Logbook Submission Mode & Safety Guardrails
/// Tab 5-7: Auto-Scheduler, Credentials, and System Requirements (Placeholders for Issue 09)
/// </summary>
public class SettingsForm : Form
{
    private readonly BackendApiClient _apiClient;
    private SaveConfigRequest _activeConfig = new();
    private readonly List<WorkProfile> _presets = new();

    // Top Level Controls
    public TabControl TabControl { get; }
    private readonly Label _lblStatus;
    private readonly Button _btnSave;
    private readonly Button _btnCancel;

    // Tab 1: WorkProfile & Applications
    private readonly TextBox _txtProfileName;
    private readonly TextBox _txtDescription;
    private readonly Button _btnPredictProfile;
    private readonly ComboBox _cboPresets;
    private readonly Panel _pnlAiBanner;
    private readonly Label _lblAiBanner;
    private readonly KeywordListPanel _keywordListPanel;
    private readonly TextBox _txtFileExtensions;

    // Tab 2: Folders & Git
    private readonly FolderListPanel _folderListPanel;

    // Tab 3: Sources, Git Frequency & Privacy
    private readonly RadioButton _rdoGitSering;
    private readonly RadioButton _rdoGitJarang;
    private readonly RadioButton _rdoGitTidak;
    private readonly CheckBox _chkGitEnabled;
    private readonly CheckBox _chkAppEnabled;
    private readonly CheckBox _chkBrowserEnabled;
    private readonly TextBox _txtAllowDomains;

    // Tab 4: Review Submission Mode
    private readonly RadioButton _rdoReview;
    private readonly RadioButton _rdoNotify;
    private readonly RadioButton _rdoAuto;
    private readonly Panel _pnlAutoWarning;
    private readonly CheckBox _chkAutoConfirm;
    private bool _isAutoWarningVisible = false;

    // Public Properties for Testing & Coordination
    public SaveConfigRequest ActiveConfig => _activeConfig;
    public FolderListPanel FolderPanel => _folderListPanel;
    public KeywordListPanel KeywordPanel => _keywordListPanel;
    public ComboBox PresetsComboBox => _cboPresets;
    public Button PredictProfileButton => _btnPredictProfile;
    public Panel AiBannerPanel => _pnlAiBanner;
    public Label AiBannerLabel => _lblAiBanner;
    private bool _isAiBannerVisible = false;
    public bool IsAiBannerVisible => _isAiBannerVisible;

    public string ProfileName
    {
        get => _txtProfileName.Text.Trim();
        set
        {
            _txtProfileName.Text = value ?? string.Empty;
            _keywordListPanel.ProfileName = value ?? string.Empty;
        }
    }

    public string NaturalDescription
    {
        get => _txtDescription.Text.Trim();
        set => _txtDescription.Text = value ?? string.Empty;
    }

    public IReadOnlyList<string> Keywords => _keywordListPanel.Keywords;

    public string FileExtensionsRawText
    {
        get => _txtFileExtensions.Text;
        set => _txtFileExtensions.Text = value ?? string.Empty;
    }

    public string AllowDomainsRawText
    {
        get => _txtAllowDomains.Text;
        set => _txtAllowDomains.Text = value ?? string.Empty;
    }

    public string GitFrequency
    {
        get
        {
            if (_rdoGitTidak.Checked) return "tidak_sama_sekali";
            if (_rdoGitJarang.Checked) return "jarang";
            return "sering";
        }
        set
        {
            switch (value?.ToLowerInvariant())
            {
                case "tidak_sama_sekali":
                    _rdoGitTidak.Checked = true;
                    break;
                case "jarang":
                    _rdoGitJarang.Checked = true;
                    break;
                default:
                    _rdoGitSering.Checked = true;
                    break;
            }
        }
    }

    public bool GitEnabled
    {
        get => _chkGitEnabled.Checked;
        set => _chkGitEnabled.Checked = value;
    }

    public bool AppEnabled
    {
        get => _chkAppEnabled.Checked;
        set => _chkAppEnabled.Checked = value;
    }

    public bool BrowserEnabled
    {
        get => _chkBrowserEnabled.Checked;
        set => _chkBrowserEnabled.Checked = value;
    }

    public string ReviewMode
    {
        get
        {
            if (_rdoAuto.Checked) return "auto";
            if (_rdoNotify.Checked) return "notify";
            return "review";
        }
        set
        {
            _rdoReview.Checked = false;
            _rdoNotify.Checked = false;
            _rdoAuto.Checked = false;

            switch (value?.ToLowerInvariant())
            {
                case "auto":
                    _rdoAuto.Checked = true;
                    break;
                case "notify":
                    _rdoNotify.Checked = true;
                    break;
                default:
                    _rdoReview.Checked = true;
                    break;
            }
            UpdateAutoWarningVisibility();
        }
    }

    public bool AutoConfirmed
    {
        get => _chkAutoConfirm.Checked;
        set => _chkAutoConfirm.Checked = value;
    }

    public bool IsAutoWarningVisible => _isAutoWarningVisible || _pnlAutoWarning.Visible;

    public bool IsGuardrailSatisfied => ReviewMode != "auto" || AutoConfirmed;

    public SettingsForm(BackendApiClient? apiClient = null)
    {
        _apiClient = apiClient ?? new BackendApiClient();

        Text = "Pengaturan Konfigurasi — MagangLog Portal";
        Size = new Size(860, 680);
        MinimumSize = new Size(800, 600);
        StartPosition = FormStartPosition.CenterParent;
        Font = new Font("Segoe UI", 9f, FontStyle.Regular);
        BackColor = Color.FromArgb(248, 250, 252);
        ShowIcon = false;
        MaximizeBox = false;
        MinimizeBox = false;

        // 1. Top Header Panel
        var headerPanel = BuildHeaderPanel();

        // 2. Bottom Action Panel
        var bottomPanel = BuildBottomPanel(out _lblStatus, out _btnSave, out _btnCancel);

        // 3. Central TabControl
        TabControl = new TabControl
        {
            Dock = DockStyle.Fill,
            Font = new Font(Font.FontFamily, 9.5f, FontStyle.Regular),
            Padding = new Point(12, 6)
        };

        // Build Tabs 1 to 4
        var tab1 = BuildTab1WorkProfile(out _txtProfileName, out _txtDescription, out _btnPredictProfile,
            out _cboPresets, out _pnlAiBanner, out _lblAiBanner, out _keywordListPanel, out _txtFileExtensions);
        var tab2 = BuildTab2Folders(out _folderListPanel);
        var tab3 = BuildTab3SourcesAndPrivacy(out _rdoGitSering, out _rdoGitJarang, out _rdoGitTidak,
            out _chkGitEnabled, out _chkAppEnabled, out _chkBrowserEnabled, out _txtAllowDomains);
        var tab4 = BuildTab4ReviewMode(out _rdoReview, out _rdoNotify, out _rdoAuto,
            out _pnlAutoWarning, out _chkAutoConfirm);

        // Placeholders for Issue 09
        var tab5 = BuildPlaceholderTab("Jadwal Otomatis", "⏰ Penjadwalan Otomatis & Windows Task Scheduler\nFitur manajemen jadwal review dan resume otomatis harian akan aktif pada Tab 5.");
        var tab6 = BuildPlaceholderTab("Kredensial & Portal", "🔑 Kredensial Gemini API & Autentikasi Portal Kemnaker\nManajemen API Key Google AI Studio dan browser login portal Monev Kemnaker.");
        var tab7 = BuildPlaceholderTab("Requirement Sistem", "📋 Pemeriksaan Requirement Host Sistem\nStatus kesehatan instalasi Python, Playwright, dan komponen pendukung aplikasi.");

        TabControl.TabPages.Add(tab1);
        TabControl.TabPages.Add(tab2);
        TabControl.TabPages.Add(tab3);
        TabControl.TabPages.Add(tab4);
        TabControl.TabPages.Add(tab5);
        TabControl.TabPages.Add(tab6);
        TabControl.TabPages.Add(tab7);

        Controls.Add(TabControl);
        Controls.Add(bottomPanel);
        Controls.Add(headerPanel);

        // Events
        _txtProfileName.TextChanged += (_, _) => _keywordListPanel.ProfileName = _txtProfileName.Text;
    }

    protected override async void OnLoad(EventArgs e)
    {
        base.OnLoad(e);
        await LoadInitialDataAsync();
    }

    /// <summary>
    /// Loads active configuration from backend and initializes all form controls.
    /// </summary>
    public async Task LoadInitialDataAsync()
    {
        try
        {
            _lblStatus.Text = "Memuat konfigurasi aktif...";
            _lblStatus.ForeColor = Color.FromArgb(71, 85, 105);

            // Fetch presets in parallel or sequentially
            var presetsTask = _apiClient.GetPresetsAsync();
            var configTask = _apiClient.GetAppConfigAsync();

            await Task.WhenAll(presetsTask, configTask);

            var presets = await presetsTask;
            if (presets != null && presets.Count > 0)
            {
                _presets.Clear();
                _presets.AddRange(presets);
                _cboPresets.Items.Clear();
                _cboPresets.Items.Add("Pilih Preset Standar...");
                foreach (var p in _presets)
                {
                    _cboPresets.Items.Add(p.ProfileName);
                }
                _cboPresets.SelectedIndex = 0;
            }

            var config = await configTask;
            if (config != null)
            {
                PopulateFromConfig(config);
                _lblStatus.Text = "Konfigurasi aktif berhasil dimuat.";
                _lblStatus.ForeColor = Color.FromArgb(22, 101, 52);
            }
            else
            {
                _lblStatus.Text = "Menggunakan konfigurasi default (belum tersimpan).";
            }
        }
        catch (Exception ex)
        {
            _lblStatus.Text = $"Gagal memuat konfigurasi: {ex.Message}";
            _lblStatus.ForeColor = Color.FromArgb(185, 28, 28);
        }
    }

    /// <summary>
    /// Populates Tab 1 to Tab 4 controls from a loaded SaveConfigRequest.
    /// </summary>
    public void PopulateFromConfig(SaveConfigRequest config)
    {
        if (config == null) return;
        _activeConfig = config;

        // Resolve WorkProfile from config.WorkProfile or config.Sources.App.WorkProfile
        var profile = config.WorkProfile ?? config.Sources?.App?.WorkProfile;
        if (profile != null)
        {
            ProfileName = profile.ProfileName;
            NaturalDescription = profile.NaturalDescription;

            var keywords = profile.ExtractKeywords();
            if (keywords.Count == 0 && profile.Applications?.Count > 0)
            {
                keywords = profile.Applications.SelectMany(a => a.ProcessNames).ToList();
            }
            _keywordListPanel.SetProfile(profile.ProfileName, keywords);

            var extensions = profile.Applications?
                .SelectMany(a => a.FileExtensions)
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .ToList() ?? new List<string>();
            SetFileExtensions(extensions);
        }
        else
        {
            _keywordListPanel.SetProfile(string.Empty, Array.Empty<string>());
            SetFileExtensions(Array.Empty<string>());
        }

        // Tab 2: Monitored Folders & Git Repositories
        var repos = config.Sources?.Git?.Repositories ?? new List<string>();
        if (repos.Count == 0 && profile?.WatchFolders?.Count > 0)
        {
            repos = profile.WatchFolders;
        }
        if (repos.Count > 0)
        {
            _ = _folderListPanel.LoadFoldersAsync(repos);
        }

        // Tab 3: Git Frequency & Individual Sources
        var gitEnabled = config.Sources?.Git?.Enabled ?? true;
        var appEnabled = config.Sources?.App?.Enabled ?? true;
        var browserEnabled = config.Sources?.Browser?.Enabled ?? false;

        if (!gitEnabled)
        {
            GitFrequency = "tidak_sama_sekali";
        }
        else if (browserEnabled)
        {
            GitFrequency = "jarang";
        }
        else
        {
            GitFrequency = "sering";
        }

        GitEnabled = gitEnabled;
        AppEnabled = appEnabled;
        BrowserEnabled = browserEnabled;

        var allowDomains = config.Sources?.Browser?.AllowDomains;
        if ((allowDomains == null || allowDomains.Count == 0) && profile?.BrowserDomains?.Count > 0)
        {
            allowDomains = profile.BrowserDomains;
        }
        SetAllowDomains(allowDomains ?? new List<string>());

        // Tab 4: Review Submission Mode
        ReviewMode = config.Review?.Mode ?? "review";
    }

    /// <summary>
    /// Writes user inputs from Tabs 1-4 back into the target configuration DTO.
    /// </summary>
    public void ApplyToConfig(SaveConfigRequest target)
    {
        target.Review ??= new ReviewSettingsDto();
        target.Review.Mode = ReviewMode;

        target.Sources ??= new SourcesSettingsDto();
        target.Sources.Git ??= new GitSourceSettingsDto();
        target.Sources.Git.Enabled = GitEnabled;
        target.Sources.Git.Repositories = _folderListPanel.GetValidFolderPaths();

        target.Sources.App ??= new AppSourceSettingsDto();
        target.Sources.App.Enabled = AppEnabled;

        target.Sources.Browser ??= new BrowserSourceSettingsDto();
        target.Sources.Browser.Enabled = BrowserEnabled;
        target.Sources.Browser.AllowDomains = GetAllowDomains();

        var profile = target.WorkProfile ?? target.Sources.App.WorkProfile ?? new WorkProfile();
        profile.ProfileName = ProfileName;
        profile.NaturalDescription = NaturalDescription;
        profile.BrowserDomains = GetAllowDomains();
        profile.WatchFolders = _folderListPanel.GetValidFolderPaths();

        var appConfig = profile.Applications.FirstOrDefault() ?? new ApplicationConfig();
        appConfig.Name = string.IsNullOrWhiteSpace(ProfileName) ? "Primary App" : ProfileName;
        appConfig.ProcessNames = _keywordListPanel.Keywords.ToList();
        appConfig.FileExtensions = GetFileExtensions();
        if (!profile.Applications.Contains(appConfig))
        {
            profile.Applications.Add(appConfig);
        }

        target.WorkProfile = profile;
        target.Sources.App.WorkProfile = profile;
    }

    /// <summary>
    /// Validates Tab 1 through 4 inputs and safety guardrails.
    /// </summary>
    public bool ValidateTabs(out string? errorMessage)
    {
        if (string.IsNullOrWhiteSpace(ProfileName))
        {
            errorMessage = "Nama profil atau peran magang pada Tab 1 tidak boleh kosong.";
            TabControl.SelectedIndex = 0;
            return false;
        }

        if (ReviewMode == "auto" && !AutoConfirmed)
        {
            errorMessage = "Mode pengiriman Otomatis memerlukan persetujuan guardrail konfirmasi pada Tab 4.";
            TabControl.SelectedIndex = 3;
            return false;
        }

        errorMessage = null;
        return true;
    }

    /// <summary>
    /// Add keyword to Tab 1 keyword panel.
    /// </summary>
    public void AddKeyword(string keyword)
    {
        _keywordListPanel.AddKeyword(keyword);
    }

    /// <summary>
    /// Normalizes and returns the list of approved web domains.
    /// </summary>
    public List<string> GetAllowDomains()
    {
        var raw = _txtAllowDomains.Text;
        if (string.IsNullOrWhiteSpace(raw)) return new List<string>();

        var separators = new[] { '\r', '\n', ',', ';' };
        var domains = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        foreach (var item in raw.Split(separators, StringSplitOptions.RemoveEmptyEntries))
        {
            var cleaned = item.Trim();
            if (cleaned.StartsWith("http://", StringComparison.OrdinalIgnoreCase))
            {
                cleaned = cleaned.Substring(7);
            }
            else if (cleaned.StartsWith("https://", StringComparison.OrdinalIgnoreCase))
            {
                cleaned = cleaned.Substring(8);
            }

            var slashIdx = cleaned.IndexOf('/');
            if (slashIdx >= 0)
            {
                cleaned = cleaned.Substring(0, slashIdx);
            }

            cleaned = cleaned.Trim().ToLowerInvariant();
            if (!string.IsNullOrEmpty(cleaned))
            {
                domains.Add(cleaned);
            }
        }

        return domains.ToList();
    }

    /// <summary>
    /// Sets the approved web domains as multiline text.
    /// </summary>
    public void SetAllowDomains(IEnumerable<string>? domains)
    {
        if (domains == null)
        {
            _txtAllowDomains.Text = string.Empty;
            return;
        }
        _txtAllowDomains.Text = string.Join(Environment.NewLine, domains);
    }

    /// <summary>
    /// Normalizes and returns the list of monitored project file extensions.
    /// </summary>
    public List<string> GetFileExtensions()
    {
        var raw = _txtFileExtensions.Text;
        if (string.IsNullOrWhiteSpace(raw)) return new List<string>();

        var separators = new[] { ',', ';', ' ', '\r', '\n' };
        var extensions = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        foreach (var item in raw.Split(separators, StringSplitOptions.RemoveEmptyEntries))
        {
            var trimmed = item.Trim().ToLowerInvariant();
            if (string.IsNullOrEmpty(trimmed)) continue;

            if (!trimmed.StartsWith("."))
            {
                trimmed = "." + trimmed;
            }
            extensions.Add(trimmed);
        }

        return extensions.ToList();
    }

    /// <summary>
    /// Sets monitored project file extensions as comma separated string.
    /// </summary>
    public void SetFileExtensions(IEnumerable<string>? extensions)
    {
        if (extensions == null)
        {
            _txtFileExtensions.Text = string.Empty;
            return;
        }
        _txtFileExtensions.Text = string.Join(", ", extensions.Select(e => e.StartsWith(".") ? e : "." + e));
    }

    #region Layout Builders

    private Panel BuildHeaderPanel()
    {
        var panel = new Panel
        {
            Dock = DockStyle.Top,
            Height = 64,
            BackColor = Color.White,
            Padding = new Padding(20, 10, 20, 10)
        };

        var lblTitle = new Label
        {
            Text = "⚙️ Pengaturan Konfigurasi Aplikasi & Integrasi",
            Dock = DockStyle.Top,
            Height = 24,
            Font = new Font(Font.FontFamily, 11f, FontStyle.Bold),
            ForeColor = Color.FromArgb(15, 23, 42)
        };

        var lblSubtitle = new Label
        {
            Text = "Sesuaikan WorkProfile, direktori repositori, preferensi privasi sumber data, dan mode pengiriman.",
            Dock = DockStyle.Top,
            Height = 20,
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Regular),
            ForeColor = Color.FromArgb(100, 116, 139)
        };

        var borderBottom = new Panel
        {
            Dock = DockStyle.Bottom,
            Height = 1,
            BackColor = Color.FromArgb(226, 232, 240)
        };

        panel.Controls.Add(lblSubtitle);
        panel.Controls.Add(lblTitle);
        panel.Controls.Add(borderBottom);
        return panel;
    }

    private Panel BuildBottomPanel(out Label lblStatus, out Button btnSave, out Button btnCancel)
    {
        var panel = new Panel
        {
            Dock = DockStyle.Bottom,
            Height = 56,
            BackColor = Color.White,
            Padding = new Padding(16, 10, 16, 10)
        };

        var borderTop = new Panel
        {
            Dock = DockStyle.Top,
            Height = 1,
            BackColor = Color.FromArgb(226, 232, 240)
        };

        lblStatus = new Label
        {
            Dock = DockStyle.Fill,
            TextAlign = ContentAlignment.MiddleLeft,
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Italic),
            ForeColor = Color.FromArgb(71, 85, 105),
            Text = "Siap."
        };

        btnCancel = new Button
        {
            Text = "Batal",
            Dock = DockStyle.Right,
            Width = 90,
            Height = 36,
            BackColor = Color.FromArgb(241, 245, 249),
            ForeColor = Color.FromArgb(71, 85, 105),
            FlatStyle = FlatStyle.Flat,
            Font = new Font(Font.FontFamily, 9f, FontStyle.Regular),
            Cursor = Cursors.Hand
        };
        btnCancel.FlatAppearance.BorderColor = Color.FromArgb(203, 213, 225);
        btnCancel.Click += (_, _) =>
        {
            DialogResult = DialogResult.Cancel;
            Close();
        };

        var spacer = new Panel { Dock = DockStyle.Right, Width = 10 };

        btnSave = new Button
        {
            Text = "💾 Simpan",
            Dock = DockStyle.Right,
            Width = 110,
            Height = 36,
            BackColor = Color.FromArgb(37, 99, 235),
            ForeColor = Color.White,
            FlatStyle = FlatStyle.Flat,
            Font = new Font(Font.FontFamily, 9f, FontStyle.Bold),
            Cursor = Cursors.Hand
        };
        btnSave.FlatAppearance.BorderSize = 0;
        btnSave.Click += (_, _) => HandleSaveClick();

        panel.Controls.Add(lblStatus);
        panel.Controls.Add(btnSave);
        panel.Controls.Add(spacer);
        panel.Controls.Add(btnCancel);
        panel.Controls.Add(borderTop);

        return panel;
    }

    private void HandleSaveClick()
    {
        if (!ValidateTabs(out var error))
        {
            MessageBox.Show(this, error, "Validasi Pengaturan", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }

        ApplyToConfig(_activeConfig);
        DialogResult = DialogResult.OK;
        Close();
    }

    private TabPage BuildTab1WorkProfile(
        out TextBox txtProfileName,
        out TextBox txtDesc,
        out Button btnPredict,
        out ComboBox cboPresets,
        out Panel pnlAiBanner,
        out Label lblAiBanner,
        out KeywordListPanel keywordPanel,
        out TextBox txtFileExts)
    {
        var page = new TabPage("WorkProfile & Aplikasi")
        {
            BackColor = Color.White,
            Padding = new Padding(12)
        };

        // Top prompt & input container
        var topContainer = new Panel
        {
            Dock = DockStyle.Top,
            Height = 150,
            Padding = new Padding(0, 0, 0, 6)
        };

        var lblProfile = new Label
        {
            Text = "Nama Peran / Profil Pekerjaan:",
            Dock = DockStyle.Top,
            Height = 20,
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Bold),
            ForeColor = Color.FromArgb(51, 65, 85)
        };

        txtProfileName = new TextBox
        {
            Dock = DockStyle.Top,
            Font = new Font(Font.FontFamily, 9.5f, FontStyle.Regular),
            PlaceholderText = "Misal: Software Engineer, UI/UX Designer, Data Analyst..."
        };

        var lblDesc = new Label
        {
            Text = "Deskripsi Tugas & Aktivitas Kerja Harian:",
            Dock = DockStyle.Top,
            Height = 22,
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Bold),
            ForeColor = Color.FromArgb(51, 65, 85),
            Padding = new Padding(0, 4, 0, 0)
        };

        txtDesc = new TextBox
        {
            Dock = DockStyle.Top,
            Multiline = true,
            Height = 44,
            Font = new Font(Font.FontFamily, 9f, FontStyle.Regular),
            ScrollBars = ScrollBars.Vertical,
            PlaceholderText = "Ceritakan aktivitas harian Anda untuk prediksi kata kunci AI..."
        };

        // Action row: Predict with AI + Presets dropdown
        var actionRow = new Panel
        {
            Dock = DockStyle.Top,
            Height = 36,
            Padding = new Padding(0, 6, 0, 0)
        };

        btnPredict = new Button
        {
            Text = "✨ Prediksi Ulang dengan AI",
            Dock = DockStyle.Left,
            Width = 190,
            Height = 30,
            BackColor = Color.FromArgb(37, 99, 235),
            ForeColor = Color.White,
            FlatStyle = FlatStyle.Flat,
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Bold),
            Cursor = Cursors.Hand
        };
        btnPredict.FlatAppearance.BorderSize = 0;
        btnPredict.Click += async (_, _) => await PredictProfileAiAsync();

        var lblOr = new Label
        {
            Text = "atau",
            Dock = DockStyle.Left,
            Width = 45,
            TextAlign = ContentAlignment.MiddleCenter,
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Regular),
            ForeColor = Color.FromArgb(100, 116, 139)
        };

        cboPresets = new ComboBox
        {
            Dock = DockStyle.Left,
            Width = 220,
            DropDownStyle = ComboBoxStyle.DropDownList,
            Font = new Font(Font.FontFamily, 9f, FontStyle.Regular)
        };
        cboPresets.Items.Add("Pilih Preset Standar...");
        cboPresets.SelectedIndex = 0;
        cboPresets.SelectedIndexChanged += (_, _) => HandlePresetSelected();

        actionRow.Controls.Add(cboPresets);
        actionRow.Controls.Add(lblOr);
        actionRow.Controls.Add(btnPredict);

        topContainer.Controls.Add(actionRow);
        topContainer.Controls.Add(txtDesc);
        topContainer.Controls.Add(lblDesc);
        topContainer.Controls.Add(txtProfileName);
        topContainer.Controls.Add(lblProfile);

        // Status feedback banner
        pnlAiBanner = new Panel
        {
            Dock = DockStyle.Top,
            Height = 32,
            Visible = false,
            BackColor = Color.FromArgb(239, 246, 255),
            Padding = new Padding(8, 6, 8, 6)
        };
        lblAiBanner = new Label
        {
            Dock = DockStyle.Fill,
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Regular),
            ForeColor = Color.FromArgb(29, 78, 216),
            TextAlign = ContentAlignment.MiddleLeft
        };
        pnlAiBanner.Controls.Add(lblAiBanner);

        // Bottom file extensions editor
        var extPanel = new Panel
        {
            Dock = DockStyle.Bottom,
            Height = 56,
            Padding = new Padding(0, 6, 0, 0)
        };

        var lblExt = new Label
        {
            Text = "Ekstensi Berkas Proyek yang Dipantau:",
            Dock = DockStyle.Top,
            Height = 18,
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Bold),
            ForeColor = Color.FromArgb(51, 65, 85)
        };

        txtFileExts = new TextBox
        {
            Dock = DockStyle.Top,
            Font = new Font(Font.FontFamily, 9.5f, FontStyle.Regular),
            PlaceholderText = "Misal: .cs, .py, .fig, .pbix, .sql, .tsx..."
        };

        extPanel.Controls.Add(txtFileExts);
        extPanel.Controls.Add(lblExt);

        // Center: KeywordListPanel
        keywordPanel = new KeywordListPanel
        {
            Dock = DockStyle.Fill
        };

        page.Controls.Add(keywordPanel);
        page.Controls.Add(extPanel);
        page.Controls.Add(pnlAiBanner);
        page.Controls.Add(topContainer);

        return page;
    }

    public async Task PredictProfileAiAsync()
    {
        var desc = NaturalDescription;
        if (string.IsNullOrWhiteSpace(desc))
        {
            ShowAiBanner("Tuliskan deskripsi aktivitas kerja harian terlebih dahulu.", isError: true);
            return;
        }

        _btnPredictProfile.Enabled = false;
        var originalText = _btnPredictProfile.Text;
        _btnPredictProfile.Text = "⏳ Memprediksi...";

        try
        {
            var res = await _apiClient.PredictProfileAsync(desc);
            if (res != null && res.Profile != null)
            {
                var profile = res.Profile;
                if (!string.IsNullOrWhiteSpace(profile.ProfileName))
                {
                    ProfileName = profile.ProfileName;
                }
                var keywords = profile.ExtractKeywords();
                _keywordListPanel.SetProfile(profile.ProfileName, keywords);

                var exts = profile.Applications?
                    .SelectMany(a => a.FileExtensions)
                    .Distinct(StringComparer.OrdinalIgnoreCase)
                    .ToList();
                if (exts != null && exts.Count > 0)
                {
                    SetFileExtensions(exts);
                }

                ShowAiBanner($"✅ Berhasil memprediksi profil dari AI ({keywords.Count} kata kunci terdeteksi).", isError: false);
            }
            else
            {
                ShowAiBanner("Tidak dapat memprediksi kata kunci dari AI. Silakan gunakan preset atau input manual.", isError: true);
            }
        }
        catch (Exception ex)
        {
            ShowAiBanner($"Gagal memprediksi: {ex.Message}", isError: true);
        }
        finally
        {
            _btnPredictProfile.Enabled = true;
            _btnPredictProfile.Text = originalText;
        }
    }

    public void HandlePresetSelected()
    {
        if (_cboPresets.SelectedIndex <= 0) return;
        var selectedName = _cboPresets.SelectedItem?.ToString();
        var preset = _presets.FirstOrDefault(p => p.ProfileName.Equals(selectedName, StringComparison.OrdinalIgnoreCase));
        if (preset != null)
        {
            ProfileName = preset.ProfileName;
            NaturalDescription = preset.NaturalDescription;
            var keywords = preset.ExtractKeywords();
            _keywordListPanel.SetProfile(preset.ProfileName, keywords);

            var exts = preset.Applications?
                .SelectMany(a => a.FileExtensions)
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .ToList();
            if (exts != null && exts.Count > 0)
            {
                SetFileExtensions(exts);
            }

            ShowAiBanner($"✅ Preset '{preset.ProfileName}' berhasil diterapkan.", isError: false);
        }
    }

    private void ShowAiBanner(string message, bool isError)
    {
        _isAiBannerVisible = true;
        _lblAiBanner.Text = message;
        _lblAiBanner.ForeColor = isError ? Color.FromArgb(185, 28, 28) : Color.FromArgb(22, 101, 52);
        _pnlAiBanner.BackColor = isError ? Color.FromArgb(254, 242, 242) : Color.FromArgb(240, 253, 244);
        _pnlAiBanner.Visible = true;
    }

    private TabPage BuildTab2Folders(out FolderListPanel folderPanel)
    {
        var page = new TabPage("Folder Proyek")
        {
            BackColor = Color.White,
            Padding = new Padding(12)
        };

        var promptPanel = new Panel
        {
            Dock = DockStyle.Top,
            Height = 44,
            Padding = new Padding(0, 0, 0, 6)
        };

        var lblTitle = new Label
        {
            Text = "Direktori Kerja & Repositori Git yang Dipantau:",
            Dock = DockStyle.Top,
            Height = 20,
            Font = new Font(Font.FontFamily, 9.5f, FontStyle.Bold),
            ForeColor = Color.FromArgb(30, 41, 59)
        };

        var lblSub = new Label
        {
            Text = "Tambahkan folder proyek lokal Anda. Sistem akan memantau commit log Git (🔀) dan perubahan berkas lokal.",
            Dock = DockStyle.Top,
            Height = 18,
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Regular),
            ForeColor = Color.FromArgb(100, 116, 139)
        };

        promptPanel.Controls.Add(lblSub);
        promptPanel.Controls.Add(lblTitle);

        folderPanel = new FolderListPanel(_apiClient)
        {
            Dock = DockStyle.Fill
        };

        page.Controls.Add(folderPanel);
        page.Controls.Add(promptPanel);

        return page;
    }

    private TabPage BuildTab3SourcesAndPrivacy(
        out RadioButton rdoSering,
        out RadioButton rdoJarang,
        out RadioButton rdoTidak,
        out CheckBox chkGit,
        out CheckBox chkApp,
        out CheckBox chkBrowser,
        out TextBox txtDomains)
    {
        var page = new TabPage("Sumber Data & Privasi")
        {
            BackColor = Color.White,
            Padding = new Padding(14),
            AutoScroll = true
        };

        // Privacy Banner at bottom
        var privacyBanner = new Panel
        {
            Dock = DockStyle.Bottom,
            Height = 56,
            BackColor = Color.FromArgb(239, 246, 255),
            BorderStyle = BorderStyle.FixedSingle,
            Padding = new Padding(12, 8, 12, 8)
        };

        var lblPrivacy = new Label
        {
            Text = "🔒 Jaminan Privasi: Seluruh pemindaian aktivitas (Git, aplikasi, browser) berjalan 100% lokal di mesin Anda. Tidak ada data pribadi atau konten rahasia yang dikirim keluar selain draf logbook resmi yang Anda setujui.",
            Dock = DockStyle.Fill,
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Regular),
            ForeColor = Color.FromArgb(29, 78, 216),
            TextAlign = ContentAlignment.MiddleLeft
        };
        privacyBanner.Controls.Add(lblPrivacy);

        // Section 1: Git Intensity Radio
        var grpGit = new GroupBox
        {
            Text = "Intensitas Penggunaan Git",
            Dock = DockStyle.Top,
            Height = 110,
            Font = new Font(Font.FontFamily, 9f, FontStyle.Bold),
            ForeColor = Color.FromArgb(30, 41, 59),
            Padding = new Padding(12)
        };

        rdoSering = new RadioButton
        {
            Text = "Sering — hampir tiap hari push/commit (fokus utama Git commits)",
            Dock = DockStyle.Top,
            Height = 24,
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Regular),
            Checked = true
        };

        rdoJarang = new RadioButton
        {
            Text = "Jarang — seimbang antara berkas dokumen, aplikasi, dan Git",
            Dock = DockStyle.Top,
            Height = 24,
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Regular)
        };

        rdoTidak = new RadioButton
        {
            Text = "Tidak sama sekali — non-coding (hanya aplikasi desktop & peramban)",
            Dock = DockStyle.Top,
            Height = 24,
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Regular)
        };

        grpGit.Controls.Add(rdoTidak);
        grpGit.Controls.Add(rdoJarang);
        grpGit.Controls.Add(rdoSering);

        // Section 2: Individual Source Checkboxes
        var grpSources = new GroupBox
        {
            Text = "Toggle Sumber Bukti Kegiatan Individual",
            Dock = DockStyle.Top,
            Height = 115,
            Font = new Font(Font.FontFamily, 9f, FontStyle.Bold),
            ForeColor = Color.FromArgb(30, 41, 59),
            Padding = new Padding(12),
            Margin = new Padding(0, 10, 0, 0)
        };

        chkGit = new CheckBox
        {
            Text = "Pantau Repositori Git & Log Commit (sources.git.enabled)",
            Dock = DockStyle.Top,
            Height = 26,
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Regular),
            Checked = true
        };

        chkApp = new CheckBox
        {
            Text = "Pantau Jendela & Proses Aplikasi Desktop Aktif (sources.app.enabled)",
            Dock = DockStyle.Top,
            Height = 26,
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Regular),
            Checked = true
        };

        chkBrowser = new CheckBox
        {
            Text = "Pantau Riwayat Peramban / Browser Disetujui (sources.browser.enabled)",
            Dock = DockStyle.Top,
            Height = 26,
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Regular),
            Checked = false
        };

        grpSources.Controls.Add(chkBrowser);
        grpSources.Controls.Add(chkApp);
        grpSources.Controls.Add(chkGit);

        // Section 3: Domain Allowlist Editor
        var pnlAllowlist = new Panel
        {
            Dock = DockStyle.Fill,
            Padding = new Padding(0, 10, 0, 10)
        };

        var lblAllowTitle = new Label
        {
            Text = "Daftar Domain Browser yang Disetujui (Approved Allowlist):",
            Dock = DockStyle.Top,
            Height = 20,
            Font = new Font(Font.FontFamily, 9f, FontStyle.Bold),
            ForeColor = Color.FromArgb(30, 41, 59)
        };

        var lblAllowSub = new Label
        {
            Text = "Batasi riwayat peramban hanya pada situs kerja resmi (satu domain per baris, mis. github.com, learn.microsoft.com):",
            Dock = DockStyle.Top,
            Height = 18,
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Regular),
            ForeColor = Color.FromArgb(100, 116, 139)
        };

        txtDomains = new TextBox
        {
            Dock = DockStyle.Fill,
            Multiline = true,
            ScrollBars = ScrollBars.Vertical,
            Font = new Font(Font.FontFamily, 9f, FontStyle.Regular),
            PlaceholderText = "github.com\nlearn.microsoft.com\nstackoverflow.com"
        };

        pnlAllowlist.Controls.Add(txtDomains);
        pnlAllowlist.Controls.Add(lblAllowSub);
        pnlAllowlist.Controls.Add(lblAllowTitle);

        page.Controls.Add(pnlAllowlist);
        page.Controls.Add(grpSources);
        page.Controls.Add(grpGit);
        page.Controls.Add(privacyBanner);

        // Wire radio sync to git checkbox
        var localTidak = rdoTidak;
        var localSering = rdoSering;
        var localJarang = rdoJarang;
        var localChkGit = chkGit;

        localTidak.CheckedChanged += (_, _) =>
        {
            if (localTidak.Checked)
            {
                localChkGit.Checked = false;
            }
        };
        localSering.CheckedChanged += (_, _) =>
        {
            if (localSering.Checked)
            {
                localChkGit.Checked = true;
            }
        };
        localJarang.CheckedChanged += (_, _) =>
        {
            if (localJarang.Checked)
            {
                localChkGit.Checked = true;
            }
        };

        return page;
    }

    private TabPage BuildTab4ReviewMode(
        out RadioButton rdoReview,
        out RadioButton rdoNotify,
        out RadioButton rdoAuto,
        out Panel pnlWarning,
        out CheckBox chkConfirm)
    {
        var page = new TabPage("Mode Pengiriman")
        {
            BackColor = Color.White,
            Padding = new Padding(14)
        };

        var lblTitle = new Label
        {
            Text = "Pilih Mode Pengiriman Logbook ke Portal Monev Kemnaker:",
            Dock = DockStyle.Top,
            Height = 24,
            Font = new Font(Font.FontFamily, 9.5f, FontStyle.Bold),
            ForeColor = Color.FromArgb(30, 41, 59)
        };

        var optionsContainer = new Panel
        {
            Dock = DockStyle.Top,
            Height = 185,
            Padding = new Padding(0, 6, 0, 6)
        };

        var reviewCard = CreateModeOptionCard(
            out rdoReview,
            "Review Dulu (Direkomendasikan)",
            "AI menyusun draf logbook harian, Anda meninjau dan menyetujuinya di dashboard sebelum dikirim ke portal Monev Kemnaker.",
            0);

        var notifyCard = CreateModeOptionCard(
            out rdoNotify,
            "Notifikasi Saja",
            "AI menyusun draf logbook secara lokal dan mengirimkan notifikasi pengingat, namun portal submission tidak dijalankan secara otomatis.",
            58);

        var autoCard = CreateModeOptionCard(
            out rdoAuto,
            "Otomatis (Full Access)",
            "AI menyusun draf dan langsung mengirimkannya secara otomatis ke portal Monev Kemnaker tanpa konfirmasi manual.",
            116);

        var localRdoReview = rdoReview;
        var localRdoNotify = rdoNotify;
        var localRdoAuto = rdoAuto;

        localRdoReview.CheckedChanged += (_, _) =>
        {
            if (localRdoReview.Checked)
            {
                localRdoNotify.Checked = false;
                localRdoAuto.Checked = false;
                UpdateAutoWarningVisibility();
            }
        };
        localRdoNotify.CheckedChanged += (_, _) =>
        {
            if (localRdoNotify.Checked)
            {
                localRdoReview.Checked = false;
                localRdoAuto.Checked = false;
                UpdateAutoWarningVisibility();
            }
        };
        localRdoAuto.CheckedChanged += (_, _) =>
        {
            if (localRdoAuto.Checked)
            {
                localRdoReview.Checked = false;
                localRdoNotify.Checked = false;
                UpdateAutoWarningVisibility();
            }
        };

        // Security Warning Panel for Auto Mode
        pnlWarning = new Panel
        {
            Dock = DockStyle.Top,
            Height = 120,
            Visible = false,
            BackColor = Color.FromArgb(254, 242, 242),
            BorderStyle = BorderStyle.FixedSingle,
            Padding = new Padding(14, 10, 14, 10)
        };

        var lblWarnTitle = new Label
        {
            Text = "⚠️ Peringatan Risiko Keamanan Mode Otomatis",
            Dock = DockStyle.Top,
            Height = 20,
            Font = new Font(Font.FontFamily, 9f, FontStyle.Bold),
            ForeColor = Color.FromArgb(185, 28, 28)
        };

        var lblWarnDesc = new Label
        {
            Text = "Draf logbook harian yang dibuat AI akan langsung dikirim ke portal Kemnaker atas nama Anda tanpa review manual. Pastikan Anda telah memeriksa keakuratan data dan konfigurasi sebelum mengaktifkan mode ini.",
            Dock = DockStyle.Top,
            Height = 36,
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Regular),
            ForeColor = Color.FromArgb(153, 27, 27)
        };

        chkConfirm = new CheckBox
        {
            Text = "Saya memahami dan menyetujui pengiriman otomatis ke portal Kemnaker tanpa review manual.",
            Dock = DockStyle.Top,
            Height = 28,
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Bold),
            ForeColor = Color.FromArgb(153, 27, 27),
            Checked = false
        };

        pnlWarning.Controls.Add(chkConfirm);
        pnlWarning.Controls.Add(lblWarnDesc);
        pnlWarning.Controls.Add(lblWarnTitle);

        optionsContainer.Controls.Add(autoCard);
        optionsContainer.Controls.Add(notifyCard);
        optionsContainer.Controls.Add(reviewCard);

        localRdoReview.Checked = true;

        page.Controls.Add(pnlWarning);
        page.Controls.Add(optionsContainer);
        page.Controls.Add(lblTitle);

        return page;
    }

    private void UpdateAutoWarningVisibility()
    {
        _isAutoWarningVisible = _rdoAuto?.Checked == true;
        if (_pnlAutoWarning != null)
        {
            _pnlAutoWarning.Visible = _isAutoWarningVisible;
        }
    }

    private Panel CreateModeOptionCard(out RadioButton rdo, string title, string description, int topOffset)
    {
        var panel = new Panel
        {
            Location = new Point(4, topOffset),
            Size = new Size(800, 52),
            BackColor = Color.FromArgb(248, 250, 252),
            BorderStyle = BorderStyle.FixedSingle,
            Padding = new Padding(8, 4, 8, 4)
        };

        rdo = new RadioButton
        {
            Text = title,
            Dock = DockStyle.Top,
            Height = 22,
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Bold),
            ForeColor = Color.FromArgb(30, 41, 59)
        };

        var lblDesc = new Label
        {
            Text = description,
            Dock = DockStyle.Top,
            Height = 22,
            Font = new Font(Font.FontFamily, 8f, FontStyle.Regular),
            ForeColor = Color.FromArgb(100, 116, 139),
            Padding = new Padding(22, 0, 0, 0)
        };

        panel.Controls.Add(lblDesc);
        panel.Controls.Add(rdo);

        var localRdo = rdo;
        panel.Click += (_, _) => localRdo.Checked = true;
        lblDesc.Click += (_, _) => localRdo.Checked = true;

        return panel;
    }

    private TabPage BuildPlaceholderTab(string tabTitle, string message)
    {
        var page = new TabPage(tabTitle)
        {
            BackColor = Color.White,
            Padding = new Padding(20)
        };

        var lbl = new Label
        {
            Text = message,
            Dock = DockStyle.Fill,
            TextAlign = ContentAlignment.MiddleCenter,
            Font = new Font(Font.FontFamily, 10f, FontStyle.Regular),
            ForeColor = Color.FromArgb(100, 116, 139)
        };

        page.Controls.Add(lbl);
        return page;
    }

    #endregion
}
