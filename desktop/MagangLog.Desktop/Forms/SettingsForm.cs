using System.Drawing;
using System.Globalization;
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
/// Tab 5: Daily Auto-Scheduler, Dual Execution Times, Active Workdays & Windows Task Scheduler
/// Tab 6: Google Gemini AI Credentials & MagangHub Kemnaker Portal Authentication
/// Tab 7: Host System Requirements Checklist & Diagnostics
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

    // Tab 5: Auto-Scheduler & Windows Task Scheduler
    private readonly CheckBox _chkSchedulerEnabled;
    private readonly DateTimePicker _dtpReviewTime;
    private readonly DateTimePicker _dtpResumeTime;
    private readonly CheckBox _chkMon;
    private readonly CheckBox _chkTue;
    private readonly CheckBox _chkWed;
    private readonly CheckBox _chkThu;
    private readonly CheckBox _chkFri;
    private readonly CheckBox _chkSat;
    private readonly CheckBox _chkSun;
    private readonly Label _lblSchedulerStatus;
    private readonly Button _btnRegisterScheduler;
    private readonly Button _btnUnregisterScheduler;
    private readonly CheckBox _chkNotifyToast;
    private readonly ComboBox _cboReminderLeadTime;
    private readonly CheckBox _chkNotifyOnSuccess;

    // Tab 6: AI Credentials & Portal
    private readonly TextBox _txtGeminiApiKey;
    private readonly CheckBox _chkShowApiKey;
    private readonly Button _btnTestGemini;
    private readonly Label _lblGeminiStatus;
    private readonly ComboBox _cboGeminiModel;
    private readonly Button _btnRefreshGeminiModels;
    private readonly Label _lblPortalStatus;
    private readonly Button _btnRefreshPortalStatus;
    private readonly Button _btnOpenPortalLogin;

    // Tab 7: Requirements Panel
    private readonly RequirementListPanel _requirementPanel;

    // Public Properties for Testing & Coordination
    public SaveConfigRequest ActiveConfig => _activeConfig;
    public FolderListPanel FolderPanel => _folderListPanel;
    public KeywordListPanel KeywordPanel => _keywordListPanel;
    public RequirementListPanel RequirementPanel => _requirementPanel;
    public ComboBox PresetsComboBox => _cboPresets;
    public Button PredictProfileButton => _btnPredictProfile;
    public Panel AiBannerPanel => _pnlAiBanner;
    public Label AiBannerLabel => _lblAiBanner;
    private bool _isAiBannerVisible = false;
    public bool IsAiBannerVisible => _isAiBannerVisible;

    // Tab 1 Properties
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

    // Tab 3 Properties
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

    // Tab 4 Properties
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

    // Tab 5 Properties
    public bool SchedulerEnabled
    {
        get => _chkSchedulerEnabled.Checked;
        set => _chkSchedulerEnabled.Checked = value;
    }

    public string ReviewTime
    {
        get => _dtpReviewTime.Value.ToString("HH:mm");
        set
        {
            if (DateTime.TryParseExact(value, "HH:mm", CultureInfo.InvariantCulture, DateTimeStyles.None, out var dt))
            {
                _dtpReviewTime.Value = dt;
            }
            else if (DateTime.TryParse(value, out dt))
            {
                _dtpReviewTime.Value = dt;
            }
        }
    }

    public string ResumeTime
    {
        get => _dtpResumeTime.Value.ToString("HH:mm");
        set
        {
            if (DateTime.TryParseExact(value, "HH:mm", CultureInfo.InvariantCulture, DateTimeStyles.None, out var dt))
            {
                _dtpResumeTime.Value = dt;
            }
            else if (DateTime.TryParse(value, out dt))
            {
                _dtpResumeTime.Value = dt;
            }
        }
    }

    public bool NotifyToast
    {
        get => _chkNotifyToast.Checked;
        set => _chkNotifyToast.Checked = value;
    }

    public bool NotifyOnSuccess
    {
        get => _chkNotifyOnSuccess.Checked;
        set => _chkNotifyOnSuccess.Checked = value;
    }

    public string SchedulerStatusText => _lblSchedulerStatus.Text;

    // Tab 6 Properties
    public string GeminiApiKey
    {
        get => _txtGeminiApiKey.Text.Trim();
        set => _txtGeminiApiKey.Text = value ?? string.Empty;
    }

    public bool ShowApiKey
    {
        get => _chkShowApiKey.Checked;
        set
        {
            _chkShowApiKey.Checked = value;
            _txtGeminiApiKey.UseSystemPasswordChar = !value;
        }
    }

    public bool IsApiKeyMasked => _txtGeminiApiKey.UseSystemPasswordChar;
    public string GeminiStatusText => _lblGeminiStatus.Text;
    public bool IsGeminiValid { get; private set; } = false;
    public string PortalStatusText => _lblPortalStatus.Text;
    public ComboBox GeminiModelComboBox => _cboGeminiModel;
    public string SelectedGeminiModel
    {
        get => _cboGeminiModel.SelectedItem?.ToString() ?? "gemini-3.5-flash";
        set
        {
            if (string.IsNullOrWhiteSpace(value)) return;
            if (!_cboGeminiModel.Items.Contains(value))
            {
                _cboGeminiModel.Items.Add(value);
            }
            _cboGeminiModel.SelectedItem = value;
        }
    }

    public SettingsForm(BackendApiClient? apiClient = null)
    {
        _apiClient = apiClient ?? new BackendApiClient();

        Text = "Pengaturan Konfigurasi — MagangLog Portal";
        Size = new Size(880, 700);
        MinimumSize = new Size(820, 620);
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

        // Build Tabs 1 to 7
        var tab1 = BuildTab1WorkProfile(out _txtProfileName, out _txtDescription, out _btnPredictProfile,
            out _cboPresets, out _pnlAiBanner, out _lblAiBanner, out _keywordListPanel, out _txtFileExtensions);
        var tab2 = BuildTab2Folders(out _folderListPanel);
        var tab3 = BuildTab3SourcesAndPrivacy(out _rdoGitSering, out _rdoGitJarang, out _rdoGitTidak,
            out _chkGitEnabled, out _chkAppEnabled, out _chkBrowserEnabled, out _txtAllowDomains);
        var tab4 = BuildTab4ReviewMode(out _rdoReview, out _rdoNotify, out _rdoAuto,
            out _pnlAutoWarning, out _chkAutoConfirm);
        var tab5 = BuildTab5Scheduler(out _chkSchedulerEnabled, out _dtpReviewTime, out _dtpResumeTime,
            out _chkMon, out _chkTue, out _chkWed, out _chkThu, out _chkFri, out _chkSat, out _chkSun,
            out _lblSchedulerStatus, out _btnRegisterScheduler, out _btnUnregisterScheduler,
            out _chkNotifyToast, out _cboReminderLeadTime, out _chkNotifyOnSuccess);
        var tab6 = BuildTab6CredentialsAndPortal(out _txtGeminiApiKey, out _chkShowApiKey, out _btnTestGemini,
            out _lblGeminiStatus, out _cboGeminiModel, out _btnRefreshGeminiModels,
            out _lblPortalStatus, out _btnRefreshPortalStatus, out _btnOpenPortalLogin);
        var tab7 = BuildTab7Requirements(out _requirementPanel);

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

            var presetsTask = _apiClient.GetPresetsAsync();
            var configTask = _apiClient.GetAppConfigAsync();
            var schedulerTask = RefreshSchedulerStatusAsync();
            var portalTask = RefreshPortalAuthStatusAsync();
            var reqTask = _requirementPanel.LoadRequirementsAsync();
            var modelsTask = LoadGeminiModelsAsync();

            await Task.WhenAll(presetsTask, configTask, schedulerTask, portalTask, reqTask, modelsTask);

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
    /// Populates Tab 1 to Tab 7 controls from a loaded SaveConfigRequest.
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

        // Tab 5: Scheduler, Workdays & Notifications
        SetWorkdays(config.Workdays);
        NotifyToast = config.Notify?.Channels?.Contains("toast") ?? true;
        NotifyOnSuccess = config.Notify?.NotifyOnSuccess ?? false;

        // Tab 6: AI Credentials
        if (config.Llm != null)
        {
            if (!string.IsNullOrWhiteSpace(config.Llm.ApiKey))
            {
                GeminiApiKey = config.Llm.ApiKey;
            }
            if (!string.IsNullOrWhiteSpace(config.Llm.Model))
            {
                SelectedGeminiModel = config.Llm.Model;
            }
        }
    }

    /// <summary>
    /// Writes user inputs from Tabs 1-7 back into the target configuration DTO.
    /// </summary>
    public void ApplyToConfig(SaveConfigRequest target)
    {
        // Tab 4
        target.Review ??= new ReviewSettingsDto();
        target.Review.Mode = ReviewMode;

        // Tab 3 & 2
        target.Sources ??= new SourcesSettingsDto();
        target.Sources.Git ??= new GitSourceSettingsDto();
        target.Sources.Git.Enabled = GitEnabled;
        target.Sources.Git.Repositories = _folderListPanel.GetValidFolderPaths();

        target.Sources.App ??= new AppSourceSettingsDto();
        target.Sources.App.Enabled = AppEnabled;

        target.Sources.Browser ??= new BrowserSourceSettingsDto();
        target.Sources.Browser.Enabled = BrowserEnabled;
        target.Sources.Browser.AllowDomains = GetAllowDomains();

        // Tab 1 WorkProfile
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

        // Tab 5: Workdays & Notifications
        target.Workdays = GetActiveWorkdays();

        target.Notify ??= new NotifySettingsDto();
        target.Notify.Channels = NotifyToast ? new List<string> { "toast" } : new List<string>();
        target.Notify.NotifyOnSuccess = NotifyOnSuccess;

        // Tab 6: LLM Credentials
        target.Llm ??= new LlmSettingsDto();
        target.Llm.ApiKey = GeminiApiKey;
        target.Llm.Model = SelectedGeminiModel;
    }

    /// <summary>
    /// Validates inputs across all tabs before saving.
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

        if (SchedulerEnabled)
        {
            var workdays = GetActiveWorkdays();
            if (workdays.Count == 0)
            {
                errorMessage = "Pilih minimal satu hari kerja aktif pada Tab 5 ketika penjadwalan otomatis diaktifkan.";
                TabControl.SelectedIndex = 4;
                return false;
            }

            var tReview = _dtpReviewTime.Value.TimeOfDay;
            var tResume = _dtpResumeTime.Value.TimeOfDay;
            if (tReview >= tResume)
            {
                errorMessage = "Jam eksekusi utama (review sore) harus lebih awal dari jam eksekusi cadangan (resume malam).";
                TabControl.SelectedIndex = 4;
                return false;
            }
        }

        errorMessage = null;
        return true;
    }

    /// <summary>
    /// Collects all inputs from Tabs 1-7, sends payload to POST /api/setup/save,
    /// registers scheduled tasks if enabled, and updates status.
    /// </summary>
    public async Task<bool> SaveAllSettingsAsync()
    {
        if (!ValidateTabs(out var error))
        {
            _lblStatus.Text = error;
            _lblStatus.ForeColor = Color.FromArgb(185, 28, 28);
            MessageBox.Show(this, error, "Validasi Pengaturan", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return false;
        }

        _btnSave.Enabled = false;
        _lblStatus.Text = "Menyimpan pengaturan ke backend...";
        _lblStatus.ForeColor = Color.FromArgb(71, 85, 105);

        try
        {
            ApplyToConfig(_activeConfig);
            var response = await _apiClient.SaveConfigAsync(_activeConfig);
            if (response != null && response.Success)
            {
                _lblStatus.Text = "Semua pengaturan berhasil disimpan.";
                _lblStatus.ForeColor = Color.FromArgb(22, 101, 52);

                if (SchedulerEnabled)
                {
                    _ = await _apiClient.RegisterSchedulerAsync(new RegisterSchedulerRequest
                    {
                        ReviewTime = ReviewTime,
                        ResumeTime = ResumeTime,
                        ActiveDays = GetActiveWorkdays(),
                        TaskPrefix = "MagangLog"
                    });
                }

                DialogResult = DialogResult.OK;
                Close();
                return true;
            }
            else
            {
                _lblStatus.Text = "Gagal menyimpan konfigurasi ke backend.";
                _lblStatus.ForeColor = Color.FromArgb(185, 28, 28);
                return false;
            }
        }
        catch (Exception ex)
        {
            _lblStatus.Text = $"Error penyimpanan: {ex.Message}";
            _lblStatus.ForeColor = Color.FromArgb(185, 28, 28);
            return false;
        }
        finally
        {
            _btnSave.Enabled = true;
        }
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

    #region Tab 5 & 6 Helpers

    public List<string> GetActiveWorkdays()
    {
        var days = new List<string>();
        if (_chkMon.Checked) days.Add("mon");
        if (_chkTue.Checked) days.Add("tue");
        if (_chkWed.Checked) days.Add("wed");
        if (_chkThu.Checked) days.Add("thu");
        if (_chkFri.Checked) days.Add("fri");
        if (_chkSat.Checked) days.Add("sat");
        if (_chkSun.Checked) days.Add("sun");
        return days;
    }

    public void SetWorkdays(IEnumerable<string>? days)
    {
        var set = new HashSet<string>(days?.Select(d => d.ToLowerInvariant()) ?? Enumerable.Empty<string>());
        _chkMon.Checked = set.Contains("mon");
        _chkTue.Checked = set.Contains("tue");
        _chkWed.Checked = set.Contains("wed");
        _chkThu.Checked = set.Contains("thu");
        _chkFri.Checked = set.Contains("fri");
        _chkSat.Checked = set.Contains("sat");
        _chkSun.Checked = set.Contains("sun");
    }

    public void SelectWeekdaysOnly()
    {
        SetWorkdays(new[] { "mon", "tue", "wed", "thu", "fri" });
    }

    public void SelectAllWorkdays()
    {
        SetWorkdays(new[] { "mon", "tue", "wed", "thu", "fri", "sat", "sun" });
    }

    public async Task RefreshSchedulerStatusAsync()
    {
        try
        {
            var res = await _apiClient.GetSchedulerStatusAsync();
            if (res != null)
            {
                if (res.IsRegistered)
                {
                    _lblSchedulerStatus.Text = $"🟢 Terdaftar Aktif ({res.ReviewTime ?? "16:30"} & {res.ResumeTime ?? "20:00"})";
                    _lblSchedulerStatus.ForeColor = Color.FromArgb(22, 101, 52);
                }
                else
                {
                    _lblSchedulerStatus.Text = "⚪ Belum Terdaftar di Windows Task Scheduler";
                    _lblSchedulerStatus.ForeColor = Color.FromArgb(100, 116, 139);
                }
            }
        }
        catch (Exception ex)
        {
            _lblSchedulerStatus.Text = $"⚠️ Gagal membaca status: {ex.Message}";
            _lblSchedulerStatus.ForeColor = Color.FromArgb(185, 28, 28);
        }
    }

    public async Task RegisterSchedulerAsync()
    {
        _btnRegisterScheduler.Enabled = false;
        try
        {
            var res = await _apiClient.RegisterSchedulerAsync(new RegisterSchedulerRequest
            {
                ReviewTime = ReviewTime,
                ResumeTime = ResumeTime,
                ActiveDays = GetActiveWorkdays(),
                TaskPrefix = "MagangLog"
            });
            if (res != null && res.Success)
            {
                _lblSchedulerStatus.Text = $"🟢 Berhasil didaftarkan ({res.ReviewTime} & {res.ResumeTime})";
                _lblSchedulerStatus.ForeColor = Color.FromArgb(22, 101, 52);
                MessageBox.Show(this, "Jadwal Windows Task Scheduler berhasil didaftarkan / diperbarui.", "Task Scheduler", MessageBoxButtons.OK, MessageBoxIcon.Information);
            }
            else
            {
                _lblSchedulerStatus.Text = "🔴 Gagal mendaftarkan jadwal Windows.";
                _lblSchedulerStatus.ForeColor = Color.FromArgb(185, 28, 28);
            }
        }
        catch (Exception ex)
        {
            _lblSchedulerStatus.Text = $"🔴 Error: {ex.Message}";
            _lblSchedulerStatus.ForeColor = Color.FromArgb(185, 28, 28);
        }
        finally
        {
            _btnRegisterScheduler.Enabled = true;
        }
    }

    public async Task UnregisterSchedulerAsync()
    {
        _btnUnregisterScheduler.Enabled = false;
        try
        {
            var res = await _apiClient.UnregisterSchedulerAsync("MagangLog");
            if (res != null && res.Success)
            {
                _lblSchedulerStatus.Text = "⚪ Tugas terjadwal berhasil dihapus.";
                _lblSchedulerStatus.ForeColor = Color.FromArgb(100, 116, 139);
                MessageBox.Show(this, "Jadwal Windows Task Scheduler berhasil dihapus dari sistem.", "Task Scheduler", MessageBoxButtons.OK, MessageBoxIcon.Information);
            }
            else
            {
                _lblSchedulerStatus.Text = "🔴 Gagal menghapus jadwal Windows.";
                _lblSchedulerStatus.ForeColor = Color.FromArgb(185, 28, 28);
            }
        }
        catch (Exception ex)
        {
            _lblSchedulerStatus.Text = $"🔴 Error: {ex.Message}";
            _lblSchedulerStatus.ForeColor = Color.FromArgb(185, 28, 28);
        }
        finally
        {
            _btnUnregisterScheduler.Enabled = true;
        }
    }

    public async Task TestGeminiConnectionAsync()
    {
        var key = GeminiApiKey;
        if (string.IsNullOrWhiteSpace(key))
        {
            _lblGeminiStatus.Text = "⚠️ Masukkan API Key terlebih dahulu.";
            _lblGeminiStatus.ForeColor = Color.FromArgb(185, 28, 28);
            IsGeminiValid = false;
            return;
        }

        _btnTestGemini.Enabled = false;
        _lblGeminiStatus.Text = "⏳ Menguji koneksi Gemini...";
        _lblGeminiStatus.ForeColor = Color.FromArgb(71, 85, 105);

        try
        {
            var res = await _apiClient.TestGeminiAsync(key);
            if (res != null && res.Valid)
            {
                IsGeminiValid = true;
                _lblGeminiStatus.Text = $"🟢 API Key Valid (Model: {res.Model})";
                _lblGeminiStatus.ForeColor = Color.FromArgb(22, 101, 52);
                await LoadGeminiModelsAsync(key);
            }
            else
            {
                IsGeminiValid = false;
                _lblGeminiStatus.Text = "🔴 Kunci API tidak valid atau kuota habis.";
                _lblGeminiStatus.ForeColor = Color.FromArgb(185, 28, 28);
            }
        }
        catch (Exception ex)
        {
            IsGeminiValid = false;
            _lblGeminiStatus.Text = $"🔴 Gagal menguji: {ex.Message}";
            _lblGeminiStatus.ForeColor = Color.FromArgb(185, 28, 28);
        }
        finally
        {
            _btnTestGemini.Enabled = true;
        }
    }

    /// <summary>
    /// Fetches live available Gemini Flash models from Google AI Studio and updates dropdown.
    /// </summary>
    public async Task LoadGeminiModelsAsync(string? key = null)
    {
        var effectiveKey = string.IsNullOrWhiteSpace(key) ? GeminiApiKey : key;
        try
        {
            _btnRefreshGeminiModels.Enabled = false;
            var response = await _apiClient.GetGeminiModelsAsync(effectiveKey);
            if (response != null && response.Models != null && response.Models.Count > 0)
            {
                var currentSelection = SelectedGeminiModel;
                _cboGeminiModel.Items.Clear();
                foreach (var m in response.Models)
                {
                    _cboGeminiModel.Items.Add(m.Id);
                }

                if (!string.IsNullOrEmpty(currentSelection) && _cboGeminiModel.Items.Contains(currentSelection))
                {
                    _cboGeminiModel.SelectedItem = currentSelection;
                }
                else
                {
                    var rec = response.Models.FirstOrDefault(m => m.IsRecommended) ?? response.Models[0];
                    _cboGeminiModel.SelectedItem = rec.Id;
                }
            }
        }
        catch
        {
            // Graceful: keep default options
        }
        finally
        {
            _btnRefreshGeminiModels.Enabled = true;
        }
    }

    public async Task RefreshPortalAuthStatusAsync()
    {
        try
        {
            var res = await _apiClient.GetPortalAuthStatusAsync();
            if (res != null && res.Authenticated)
            {
                _lblPortalStatus.Text = $"🟢 Sesi Aktif ({res.Username ?? "User Terautentikasi"})";
                _lblPortalStatus.ForeColor = Color.FromArgb(22, 101, 52);
            }
            else
            {
                _lblPortalStatus.Text = "⚪ Belum Login / Sesi Kedaluwarsa";
                _lblPortalStatus.ForeColor = Color.FromArgb(100, 116, 139);
            }
        }
        catch (Exception ex)
        {
            _lblPortalStatus.Text = $"⚠️ Gagal membaca status: {ex.Message}";
            _lblPortalStatus.ForeColor = Color.FromArgb(185, 28, 28);
        }
    }

    public async Task OpenPortalLoginAsync()
    {
        _btnOpenPortalLogin.Enabled = false;
        _lblPortalStatus.Text = "⏳ Meluncurkan peramban interaktif Playwright...";
        _lblPortalStatus.ForeColor = Color.FromArgb(71, 85, 105);

        try
        {
            var res = await _apiClient.OpenPortalLoginAsync(180);
            if (res != null && res.Success)
            {
                _lblPortalStatus.Text = res.Authenticated ? "🟢 Login Berhasil!" : "ℹ️ Sesi login selesai.";
                _lblPortalStatus.ForeColor = Color.FromArgb(22, 101, 52);
                await RefreshPortalAuthStatusAsync();
            }
            else
            {
                _lblPortalStatus.Text = $"🔴 {res?.Message ?? "Gagal membuka login."}";
                _lblPortalStatus.ForeColor = Color.FromArgb(185, 28, 28);
            }
        }
        catch (Exception ex)
        {
            _lblPortalStatus.Text = $"🔴 Error: {ex.Message}";
            _lblPortalStatus.ForeColor = Color.FromArgb(185, 28, 28);
        }
        finally
        {
            _btnOpenPortalLogin.Enabled = true;
        }
    }

    #endregion

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
            Text = "Sesuaikan WorkProfile, direktori repositori, penjadwalan otomatis, kredensial AI, dan status portal.",
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
            Text = "💾 Simpan Semua Pengaturan",
            Dock = DockStyle.Right,
            Width = 210,
            Height = 36,
            BackColor = Color.FromArgb(37, 99, 235),
            ForeColor = Color.White,
            FlatStyle = FlatStyle.Flat,
            Font = new Font(Font.FontFamily, 9f, FontStyle.Bold),
            Cursor = Cursors.Hand
        };
        btnSave.FlatAppearance.BorderSize = 0;
        btnSave.Click += async (_, _) => await SaveAllSettingsAsync();

        panel.Controls.Add(lblStatus);
        panel.Controls.Add(btnSave);
        panel.Controls.Add(spacer);
        panel.Controls.Add(btnCancel);
        panel.Controls.Add(borderTop);

        return panel;
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

    private TabPage BuildTab5Scheduler(
        out CheckBox chkEnabled,
        out DateTimePicker dtpReview,
        out DateTimePicker dtpResume,
        out CheckBox chkMon,
        out CheckBox chkTue,
        out CheckBox chkWed,
        out CheckBox chkThu,
        out CheckBox chkFri,
        out CheckBox chkSat,
        out CheckBox chkSun,
        out Label lblStatus,
        out Button btnRegister,
        out Button btnUnregister,
        out CheckBox chkNotifyToast,
        out ComboBox cboLeadTime,
        out CheckBox chkNotifySuccess)
    {
        var page = new TabPage("Jadwal Otomatis")
        {
            BackColor = Color.White,
            Padding = new Padding(14),
            AutoScroll = true
        };

        // 1. Enable Daily Automation Checkbox
        chkEnabled = new CheckBox
        {
            Text = "Aktifkan Penjadwalan Otomatis Harian (scheduler.enabled)",
            Dock = DockStyle.Top,
            Height = 28,
            Font = new Font(Font.FontFamily, 9.5f, FontStyle.Bold),
            ForeColor = Color.FromArgb(30, 41, 59),
            Checked = true
        };

        // 2. Dual Execution Time Picker Group
        var grpTimes = new GroupBox
        {
            Text = "Jam Eksekusi Harian (WIB)",
            Dock = DockStyle.Top,
            Height = 85,
            Font = new Font(Font.FontFamily, 9f, FontStyle.Bold),
            ForeColor = Color.FromArgb(30, 41, 59),
            Padding = new Padding(12)
        };

        var lblReview = new Label
        {
            Text = "Draf Sore:",
            Location = new Point(14, 28),
            Size = new Size(80, 24),
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Regular)
        };
        dtpReview = new DateTimePicker
        {
            Format = DateTimePickerFormat.Custom,
            CustomFormat = "HH:mm",
            ShowUpDown = true,
            Location = new Point(96, 26),
            Size = new Size(80, 24),
            Font = new Font(Font.FontFamily, 9.5f, FontStyle.Bold),
            Value = DateTime.Today.AddHours(16).AddMinutes(30)
        };

        var lblResume = new Label
        {
            Text = "Resume Malam:",
            Location = new Point(220, 28),
            Size = new Size(100, 24),
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Regular)
        };
        dtpResume = new DateTimePicker
        {
            Format = DateTimePickerFormat.Custom,
            CustomFormat = "HH:mm",
            ShowUpDown = true,
            Location = new Point(325, 26),
            Size = new Size(80, 24),
            Font = new Font(Font.FontFamily, 9.5f, FontStyle.Bold),
            Value = DateTime.Today.AddHours(20)
        };

        grpTimes.Controls.Add(lblReview);
        grpTimes.Controls.Add(dtpReview);
        grpTimes.Controls.Add(lblResume);
        grpTimes.Controls.Add(dtpResume);

        // 3. Active Workdays Selection Group
        var grpDays = new GroupBox
        {
            Text = "Pilihan Hari Kerja Aktif",
            Dock = DockStyle.Top,
            Height = 100,
            Font = new Font(Font.FontFamily, 9f, FontStyle.Bold),
            ForeColor = Color.FromArgb(30, 41, 59),
            Padding = new Padding(12)
        };

        chkMon = new CheckBox { Text = "Senin", Location = new Point(16, 24), Size = new Size(65, 22), Checked = true };
        chkTue = new CheckBox { Text = "Selasa", Location = new Point(85, 24), Size = new Size(65, 22), Checked = true };
        chkWed = new CheckBox { Text = "Rabu", Location = new Point(155, 24), Size = new Size(65, 22), Checked = true };
        chkThu = new CheckBox { Text = "Kamis", Location = new Point(225, 24), Size = new Size(65, 22), Checked = true };
        chkFri = new CheckBox { Text = "Jumat", Location = new Point(295, 24), Size = new Size(65, 22), Checked = true };
        chkSat = new CheckBox { Text = "Sabtu", Location = new Point(365, 24), Size = new Size(65, 22), Checked = false };
        chkSun = new CheckBox { Text = "Minggu", Location = new Point(435, 24), Size = new Size(70, 22), Checked = false };

        var btnWeekdays = new Button
        {
            Text = "Hari Kerja (Senin–Jumat)",
            Location = new Point(16, 56),
            Size = new Size(170, 28),
            BackColor = Color.FromArgb(241, 245, 249),
            FlatStyle = FlatStyle.Flat,
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Regular),
            Cursor = Cursors.Hand
        };
        btnWeekdays.Click += (_, _) => SelectWeekdaysOnly();

        var btnAllDays = new Button
        {
            Text = "Pilih Semua",
            Location = new Point(195, 56),
            Size = new Size(110, 28),
            BackColor = Color.FromArgb(241, 245, 249),
            FlatStyle = FlatStyle.Flat,
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Regular),
            Cursor = Cursors.Hand
        };
        btnAllDays.Click += (_, _) => SelectAllWorkdays();

        grpDays.Controls.Add(chkMon);
        grpDays.Controls.Add(chkTue);
        grpDays.Controls.Add(chkWed);
        grpDays.Controls.Add(chkThu);
        grpDays.Controls.Add(chkFri);
        grpDays.Controls.Add(chkSat);
        grpDays.Controls.Add(chkSun);
        grpDays.Controls.Add(btnWeekdays);
        grpDays.Controls.Add(btnAllDays);

        // 4. Windows Task Scheduler Integration Group
        var grpScheduler = new GroupBox
        {
            Text = "Integrasi Windows Task Scheduler",
            Dock = DockStyle.Top,
            Height = 110,
            Font = new Font(Font.FontFamily, 9f, FontStyle.Bold),
            ForeColor = Color.FromArgb(30, 41, 59),
            Padding = new Padding(12)
        };

        lblStatus = new Label
        {
            Text = "⚪ Memeriksa status registrasi Task Scheduler...",
            Location = new Point(16, 26),
            Size = new Size(600, 22),
            Font = new Font(Font.FontFamily, 9f, FontStyle.Bold),
            ForeColor = Color.FromArgb(71, 85, 105)
        };

        btnRegister = new Button
        {
            Text = "📅 Daftarkan / Perbarui Jadwal Windows",
            Location = new Point(16, 56),
            Size = new Size(245, 32),
            BackColor = Color.FromArgb(37, 99, 235),
            ForeColor = Color.White,
            FlatStyle = FlatStyle.Flat,
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Bold),
            Cursor = Cursors.Hand
        };
        btnRegister.FlatAppearance.BorderSize = 0;
        btnRegister.Click += async (_, _) => await RegisterSchedulerAsync();

        btnUnregister = new Button
        {
            Text = "🗑️ Hapus Jadwal Windows",
            Location = new Point(275, 56),
            Size = new Size(180, 32),
            BackColor = Color.FromArgb(241, 245, 249),
            ForeColor = Color.FromArgb(185, 28, 28),
            FlatStyle = FlatStyle.Flat,
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Bold),
            Cursor = Cursors.Hand
        };
        btnUnregister.FlatAppearance.BorderColor = Color.FromArgb(252, 165, 165);
        btnUnregister.Click += async (_, _) => await UnregisterSchedulerAsync();

        grpScheduler.Controls.Add(lblStatus);
        grpScheduler.Controls.Add(btnRegister);
        grpScheduler.Controls.Add(btnUnregister);

        // 5. Desktop Notifications Preferences
        var grpNotify = new GroupBox
        {
            Text = "Preferensi Notifikasi Desktop",
            Dock = DockStyle.Top,
            Height = 110,
            Font = new Font(Font.FontFamily, 9f, FontStyle.Bold),
            ForeColor = Color.FromArgb(30, 41, 59),
            Padding = new Padding(12)
        };

        chkNotifyToast = new CheckBox
        {
            Text = "Kirim Notifikasi Windows Toast (notify.channels)",
            Location = new Point(16, 24),
            Size = new Size(350, 22),
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Regular),
            Checked = true
        };

        var lblLeadTime = new Label
        {
            Text = "Waktu Pengingat Awal:",
            Location = new Point(16, 56),
            Size = new Size(140, 22),
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Regular)
        };

        cboLeadTime = new ComboBox
        {
            Location = new Point(160, 54),
            Size = new Size(160, 24),
            DropDownStyle = ComboBoxStyle.DropDownList,
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Regular)
        };
        cboLeadTime.Items.AddRange(new object[] { "Tepat Waktu", "15 Menit Sebelum", "30 Menit Sebelum", "60 Menit Sebelum" });
        cboLeadTime.SelectedIndex = 1;

        chkNotifySuccess = new CheckBox
        {
            Text = "Notifikasi status sukses (meskipun tanpa aksi manual)",
            Location = new Point(340, 56),
            Size = new Size(380, 22),
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Regular),
            Checked = false
        };

        grpNotify.Controls.Add(chkNotifyToast);
        grpNotify.Controls.Add(lblLeadTime);
        grpNotify.Controls.Add(cboLeadTime);
        grpNotify.Controls.Add(chkNotifySuccess);

        page.Controls.Add(grpNotify);
        page.Controls.Add(grpScheduler);
        page.Controls.Add(grpDays);
        page.Controls.Add(grpTimes);
        page.Controls.Add(chkEnabled);

        return page;
    }

    private TabPage BuildTab6CredentialsAndPortal(
        out TextBox txtApiKey,
        out CheckBox chkShow,
        out Button btnTest,
        out Label lblGeminiStatus,
        out ComboBox cboGeminiModel,
        out Button btnRefreshModels,
        out Label lblPortalStatus,
        out Button btnRefreshPortal,
        out Button btnOpenLogin)
    {
        var page = new TabPage("Kredensial & Portal")
        {
            BackColor = Color.White,
            Padding = new Padding(14),
            AutoScroll = true
        };

        // 1. Google Gemini AI Credentials Group
        var grpGemini = new GroupBox
        {
            Text = "Kredensial Google AI Studio (Gemini)",
            Dock = DockStyle.Top,
            Height = 225,
            Font = new Font(Font.FontFamily, 9f, FontStyle.Bold),
            ForeColor = Color.FromArgb(30, 41, 59),
            Padding = new Padding(12)
        };

        var lblKey = new Label
        {
            Text = "Google AI Studio API Key:",
            Location = new Point(14, 26),
            Size = new Size(200, 20),
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Regular)
        };

        txtApiKey = new TextBox
        {
            Location = new Point(16, 48),
            Size = new Size(520, 26),
            UseSystemPasswordChar = true,
            Font = new Font("Consolas", 9.5f, FontStyle.Regular),
            PlaceholderText = "Tempel API key Google AI Studio (AIzaSy...)"
        };

        chkShow = new CheckBox
        {
            Text = "Tampilkan Kunci",
            Location = new Point(545, 50),
            Size = new Size(120, 22),
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Regular)
        };
        var localTxtApiKey = txtApiKey;
        var localChkShow = chkShow;
        localChkShow.CheckedChanged += (_, _) => localTxtApiKey.UseSystemPasswordChar = !localChkShow.Checked;

        var lblModel = new Label
        {
            Text = "Model Gemini Terpilih (Free Tier):",
            Location = new Point(14, 82),
            Size = new Size(250, 18),
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Regular)
        };

        cboGeminiModel = new ComboBox
        {
            Location = new Point(16, 102),
            Size = new Size(350, 26),
            DropDownStyle = ComboBoxStyle.DropDownList,
            Font = new Font("Segoe UI", 9f, FontStyle.Regular)
        };
        cboGeminiModel.Items.AddRange(new object[]
        {
            "gemini-3.5-flash",
            "gemini-3.8-flash",
            "gemini-flash-latest",
            "gemini-3.7-flash"
        });
        cboGeminiModel.SelectedItem = "gemini-3.5-flash";

        btnRefreshModels = new Button
        {
            Text = "🔄 Perbarui Model",
            Location = new Point(376, 100),
            Size = new Size(160, 28),
            BackColor = Color.FromArgb(241, 245, 249),
            ForeColor = Color.FromArgb(30, 41, 59),
            FlatStyle = FlatStyle.Flat,
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Regular),
            Cursor = Cursors.Hand
        };
        btnRefreshModels.FlatAppearance.BorderColor = Color.FromArgb(203, 213, 225);
        btnRefreshModels.Click += async (_, _) => await LoadGeminiModelsAsync(localTxtApiKey.Text);

        btnTest = new Button
        {
            Text = "⚡ Tes Koneksi Gemini",
            Location = new Point(16, 142),
            Size = new Size(170, 32),
            BackColor = Color.FromArgb(37, 99, 235),
            ForeColor = Color.White,
            FlatStyle = FlatStyle.Flat,
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Bold),
            Cursor = Cursors.Hand
        };
        btnTest.FlatAppearance.BorderSize = 0;
        btnTest.Click += async (_, _) => await TestGeminiConnectionAsync();

        lblGeminiStatus = new Label
        {
            Text = "Status: Belum diuji",
            Location = new Point(195, 149),
            Size = new Size(480, 22),
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Regular),
            ForeColor = Color.FromArgb(100, 116, 139)
        };

        var lblKeyNote = new Label
        {
            Text = "ℹ️ Kunci API disimpan lokal dan model dipilih otomatis dari daftar aktif Google AI Studio.",
            Location = new Point(16, 186),
            Size = new Size(650, 20),
            Font = new Font(Font.FontFamily, 8f, FontStyle.Italic),
            ForeColor = Color.FromArgb(100, 116, 139)
        };

        grpGemini.Controls.Add(lblKey);
        grpGemini.Controls.Add(txtApiKey);
        grpGemini.Controls.Add(chkShow);
        grpGemini.Controls.Add(lblModel);
        grpGemini.Controls.Add(cboGeminiModel);
        grpGemini.Controls.Add(btnRefreshModels);
        grpGemini.Controls.Add(btnTest);
        grpGemini.Controls.Add(lblGeminiStatus);
        grpGemini.Controls.Add(lblKeyNote);

        // 2. MagangHub Kemnaker Portal Authentication Group
        var grpPortal = new GroupBox
        {
            Text = "Sesi & Autentikasi Portal Monev Kemnaker",
            Dock = DockStyle.Top,
            Height = 170,
            Font = new Font(Font.FontFamily, 9f, FontStyle.Bold),
            ForeColor = Color.FromArgb(30, 41, 59),
            Padding = new Padding(12),
            Margin = new Padding(0, 12, 0, 0)
        };

        lblPortalStatus = new Label
        {
            Text = "⚪ Memeriksa status sesi portal...",
            Location = new Point(16, 28),
            Size = new Size(600, 24),
            Font = new Font(Font.FontFamily, 9f, FontStyle.Bold),
            ForeColor = Color.FromArgb(71, 85, 105)
        };

        btnRefreshPortal = new Button
        {
            Text = "🔄 Cek Status Sesi",
            Location = new Point(16, 60),
            Size = new Size(150, 32),
            BackColor = Color.FromArgb(241, 245, 249),
            FlatStyle = FlatStyle.Flat,
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Regular),
            Cursor = Cursors.Hand
        };
        btnRefreshPortal.Click += async (_, _) => await RefreshPortalAuthStatusAsync();

        btnOpenLogin = new Button
        {
            Text = "🌐 Buka Browser Login Portal",
            Location = new Point(175, 60),
            Size = new Size(220, 32),
            BackColor = Color.FromArgb(16, 185, 129),
            ForeColor = Color.White,
            FlatStyle = FlatStyle.Flat,
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Bold),
            Cursor = Cursors.Hand
        };
        btnOpenLogin.FlatAppearance.BorderSize = 0;
        btnOpenLogin.Click += async (_, _) => await OpenPortalLoginAsync();

        var lblPortalHelp = new Label
        {
            Text = "Tombol di atas meluncurkan peramban interaktif Playwright untuk login ke akun Monev Kemnaker Anda. Setelah Anda masuk, status autentikasi disimpan aman di storage state lokal.",
            Location = new Point(16, 102),
            Size = new Size(680, 45),
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Regular),
            ForeColor = Color.FromArgb(100, 116, 139)
        };

        grpPortal.Controls.Add(lblPortalStatus);
        grpPortal.Controls.Add(btnRefreshPortal);
        grpPortal.Controls.Add(btnOpenLogin);
        grpPortal.Controls.Add(lblPortalHelp);

        page.Controls.Add(grpPortal);
        page.Controls.Add(grpGemini);

        return page;
    }

    private TabPage BuildTab7Requirements(out RequirementListPanel requirementPanel)
    {
        var page = new TabPage("Requirement Sistem")
        {
            BackColor = Color.White,
            Padding = new Padding(12)
        };

        var topBar = new Panel
        {
            Dock = DockStyle.Top,
            Height = 44,
            Padding = new Padding(0, 0, 0, 8)
        };

        var btnRecheck = new Button
        {
            Text = "🔄 Cek Ulang Semua Requirement",
            Dock = DockStyle.Left,
            Width = 240,
            Height = 34,
            BackColor = Color.FromArgb(241, 245, 249),
            ForeColor = Color.FromArgb(30, 41, 59),
            FlatStyle = FlatStyle.Flat,
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Bold),
            Cursor = Cursors.Hand
        };
        btnRecheck.FlatAppearance.BorderColor = Color.FromArgb(203, 213, 225);

        topBar.Controls.Add(btnRecheck);

        requirementPanel = new RequirementListPanel(_apiClient)
        {
            Dock = DockStyle.Fill
        };

        var localReqPanel = requirementPanel;
        btnRecheck.Click += async (_, _) => await localReqPanel.LoadRequirementsAsync();

        page.Controls.Add(requirementPanel);
        page.Controls.Add(topBar);

        return page;
    }

    #endregion
}
