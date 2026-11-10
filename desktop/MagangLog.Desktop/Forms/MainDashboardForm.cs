using System.Diagnostics;
using MagangLog.Desktop.Controls;
using MagangLog.Desktop.Models;
using MagangLog.Desktop.Services;

namespace MagangLog.Desktop.Forms;

/// <summary>
/// Main desktop dashboard window for monitoring, review, calendar, and settings.
/// Serves as the primary control center for daily intern log compliance.
/// </summary>
public class MainDashboardForm : Form
{
    private readonly BackendApiClient _apiClient;
    private readonly Label _lblTitle;
    private readonly Button _btnOpenWizard;
    private readonly Button _btnSettings;
    private readonly Button _btnAbout;

    public StatusBannerPanel StatusBanner { get; }
    public SplitContainer MainSplitContainer { get; }
    public CalendarPanel CalendarPanel { get; }
    public EvidencePanel EvidencePanel { get; }
    public DraftEditorPanel DraftEditor { get; }
    public FallbackNotePanel FallbackNote { get; }
    public DashboardMode CurrentMode { get; private set; } = DashboardMode.DraftEditor;
    public System.Windows.Forms.Timer PollingTimer { get; }

    public bool OnboardingComplete { get; set; } = false;
    public string ConfigFilePath { get; set; } = "config/config.yaml";
    public string PortalUrl { get; set; } = "https://monev.maganghub.kemnaker.go.id/dashboard/riwayat";

    public Action<DayDetailForm>? DayDetailShower { get; set; }
    public Action<AboutForm>? AboutDialogShower { get; set; }
    public Action<SettingsForm>? SettingsDialogShower { get; set; }

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
                $"Gagal membuka browser default: {ex.Message}",
                "Kesalahan Peramban",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
        }
    };

    public MainDashboardForm(BackendApiClient? apiClient = null)
    {
        _apiClient = apiClient ?? new BackendApiClient();

        Text = "Local Dashboard — Magang Log";
        StartPosition = FormStartPosition.CenterScreen;
        Size = new Size(1024, 720);
        MinimumSize = new Size(800, 600);
        BackColor = Color.FromArgb(248, 250, 252);

        // 1. Header Bar (Dock Top)
        var headerPanel = new Panel
        {
            Dock = DockStyle.Top,
            Height = 58,
            BackColor = Color.White,
            Padding = new Padding(24, 12, 24, 12)
        };

        _lblTitle = new Label
        {
            Text = "Magang Log — Local Dashboard",
            Font = new Font(Font.FontFamily, 13f, FontStyle.Bold),
            ForeColor = Color.FromArgb(15, 23, 42),
            Dock = DockStyle.Left,
            AutoSize = true,
            TextAlign = ContentAlignment.MiddleLeft
        };

        var headerBtnFlow = new FlowLayoutPanel
        {
            Dock = DockStyle.Right,
            FlowDirection = FlowDirection.RightToLeft,
            AutoSize = true,
            BackColor = Color.Transparent,
            WrapContents = false
        };

        _btnOpenWizard = new Button
        {
            Text = "Buka Setup Wizard",
            Height = 32,
            AutoSize = true,
            Padding = new Padding(12, 0, 12, 0),
            BackColor = Color.FromArgb(241, 245, 249),
            ForeColor = Color.FromArgb(30, 41, 59),
            FlatStyle = FlatStyle.Flat,
            Cursor = Cursors.Hand,
            Margin = new Padding(6, 0, 0, 0),
            Font = new Font(Font.FontFamily, 9f, FontStyle.Regular)
        };
        _btnOpenWizard.FlatAppearance.BorderColor = Color.FromArgb(203, 213, 225);
        _btnOpenWizard.Click += (_, _) => LaunchSetupWizard();

        _btnSettings = new Button
        {
            Text = "Pengaturan ⚙️",
            Height = 32,
            AutoSize = true,
            Padding = new Padding(12, 0, 12, 0),
            BackColor = Color.FromArgb(241, 245, 249),
            ForeColor = Color.FromArgb(30, 41, 59),
            FlatStyle = FlatStyle.Flat,
            Cursor = Cursors.Hand,
            Margin = new Padding(6, 0, 0, 0),
            Font = new Font(Font.FontFamily, 9f, FontStyle.Regular)
        };
        _btnSettings.FlatAppearance.BorderColor = Color.FromArgb(203, 213, 225);
        _btnSettings.Click += (_, _) => LaunchSettings();

        _btnAbout = new Button
        {
            Text = "Tentang ℹ️",
            Height = 32,
            AutoSize = true,
            Padding = new Padding(12, 0, 12, 0),
            BackColor = Color.FromArgb(241, 245, 249),
            ForeColor = Color.FromArgb(30, 41, 59),
            FlatStyle = FlatStyle.Flat,
            Cursor = Cursors.Hand,
            Margin = new Padding(6, 0, 0, 0),
            Font = new Font(Font.FontFamily, 9f, FontStyle.Regular)
        };
        _btnAbout.FlatAppearance.BorderColor = Color.FromArgb(203, 213, 225);
        _btnAbout.Click += (_, _) => LaunchAbout();

        headerBtnFlow.Controls.Add(_btnOpenWizard);
        headerBtnFlow.Controls.Add(_btnSettings);
        headerBtnFlow.Controls.Add(_btnAbout);

        headerPanel.Controls.Add(_lblTitle);
        headerPanel.Controls.Add(headerBtnFlow);

        // 2. Status Hero Banner (Dock Top below Header)
        StatusBanner = new StatusBannerPanel();
        StatusBanner.OpenPortalButton.Click += (_, _) => OpenPortal();
        StatusBanner.RunPipelineButton.Click += async (_, _) => await RunPipelineManualAsync();

        // 3. Bottom Monthly Calendar Panel
        CalendarPanel = new CalendarPanel(_apiClient)
        {
            Dock = DockStyle.Bottom,
            Height = 210,
            BorderStyle = BorderStyle.FixedSingle
        };
        CalendarPanel.OnDaySelected += async cell => await ShowDayDetailAsync(cell);
        DayDetailShower = form => form.ShowDialog(this);
        AboutDialogShower = form => form.ShowDialog(this);
        SettingsDialogShower = form => form.ShowDialog(this);

        // 4. Middle Responsive Content (SplitContainer)
        MainSplitContainer = new SplitContainer
        {
            Dock = DockStyle.Fill,
            Orientation = Orientation.Vertical,
            SplitterWidth = 8,
            BackColor = Color.FromArgb(241, 245, 249)
        };

        // Left Panel (Panel1: Draft Editor & Quick Notes Fallback)
        DraftEditor = new DraftEditorPanel(_apiClient);
        DraftEditor.OnDraftUpdated += async () => await RefreshStatusAsync();

        FallbackNote = new FallbackNotePanel(_apiClient);
        FallbackNote.OnNoteSubmitted += async () => await RefreshStatusAsync();
        FallbackNote.OnSwitchToEditorRequested += () => SetDashboardMode(DashboardMode.DraftEditor);
        FallbackNote.Visible = false;

        MainSplitContainer.Panel1.Controls.Add(FallbackNote);
        MainSplitContainer.Panel1.Controls.Add(DraftEditor);

        // Right Panel (Panel2: Evidence Feed)
        EvidencePanel = new EvidencePanel();
        MainSplitContainer.Panel2.Controls.Add(EvidencePanel);

        // Adjust initial splitter proportions (~65-70% left, ~30-35% right)
        MainSplitContainer.SplitterDistance = Math.Max(200, (int)(Width * 0.68));

        // Add controls in reverse dock order:
        // Fill first, then Bottom, then Top banners
        Controls.Add(MainSplitContainer);
        Controls.Add(CalendarPanel);
        Controls.Add(StatusBanner);
        Controls.Add(headerPanel);

        // 5. Polling Timer (60s)
        PollingTimer = new System.Windows.Forms.Timer
        {
            Interval = 60000
        };
        PollingTimer.Tick += async (_, _) => await RefreshStatusAsync();
    }

    protected override void OnLoad(EventArgs e)
    {
        base.OnLoad(e);

        if (IsOnboardingRequired())
        {
            LaunchSetupWizard();
        }

        PollingTimer.Start();
        _ = RefreshStatusAsync();
    }

    /// <summary>
    /// Fetch today's status from backend and refresh status banner.
    /// Safely catches network exceptions and sets banner to offline status.
    /// </summary>
    public async Task RefreshStatusAsync()
    {
        try
        {
            var statusTask = _apiClient.GetTodayStatusAsync();
            var evidenceTask = _apiClient.GetEvidenceTodayAsync();
            var entryTask = _apiClient.GetTodayEntryAsync();
            var calendarTask = CalendarPanel.LoadMonthAsync(CalendarPanel.CurrentYear, CalendarPanel.CurrentMonth);

            await Task.WhenAll(statusTask, evidenceTask, entryTask, calendarTask);

            var status = await statusTask;
            var evidence = await evidenceTask;
            var entry = await entryTask;

            if (status == null)
            {
                StatusBanner.UpdateOffline();
            }
            else
            {
                StatusBanner.UpdateStatus(status);
            }

            EvidencePanel.SetEvidenceItems(evidence);
            DraftEditor.LoadEntry(entry);
            FallbackNote.SetTargetDate(status?.TargetDate);

            var resolvedMode = DashboardModeResolver.ResolveMode(status, entry);
            SetDashboardMode(resolvedMode);
        }
        catch (Exception)
        {
            StatusBanner.UpdateOffline();
            EvidencePanel.SetEvidenceItems(null);
            DraftEditor.LoadEntry(null);
            SetDashboardMode(DashboardMode.DraftEditor);
        }
    }

    /// <summary>
    /// Open DayDetailForm modal for selected calendar date.
    /// </summary>
    public async Task ShowDayDetailAsync(CalendarDayCellModel cell)
    {
        if (string.IsNullOrWhiteSpace(cell.DateString))
        {
            return;
        }

        EntryDetailResponse? entry = null;
        try
        {
            entry = await _apiClient.GetTodayEntryAsync(cell.DateString);
        }
        catch (Exception)
        {
            entry = null;
        }

        using var dialog = new DayDetailForm(cell.DateString, entry, _apiClient);
        DayDetailShower?.Invoke(dialog);
    }

    /// <summary>
    /// Switch active mode between DraftEditor and FallbackNote.
    /// </summary>
    public void SetDashboardMode(DashboardMode mode)
    {
        CurrentMode = mode;
        if (mode == DashboardMode.FallbackNote)
        {
            FallbackNote.Visible = true;
            DraftEditor.Visible = false;
        }
        else
        {
            FallbackNote.Visible = false;
            DraftEditor.Visible = true;
        }
    }

    public bool IsFallbackNoteVisible => CurrentMode == DashboardMode.FallbackNote;
    public bool IsDraftEditorVisible => CurrentMode == DashboardMode.DraftEditor;

    /// <summary>
    /// Trigger manual pipeline execution and refresh today's status.
    /// </summary>
    public async Task RunPipelineManualAsync()
    {
        StatusBanner.SetPipelineRunning(true);
        try
        {
            var success = await _apiClient.TriggerPipelineAsync();
            if (!success)
            {
                StatusBanner.UpdateOffline();
            }
        }
        catch (Exception)
        {
            StatusBanner.UpdateOffline();
        }
        finally
        {
            StatusBanner.SetPipelineRunning(false);
            await RefreshStatusAsync();
        }
    }

    /// <summary>
    /// Open Kemnaker Monev portal in default web browser.
    /// </summary>
    public void OpenPortal()
    {
        UrlOpener.Invoke(PortalUrl);
    }

    /// <summary>
    /// Open Settings reconfiguration dialog.
    /// </summary>
    public void LaunchSettings()
    {
        using var settingsForm = new SettingsForm(_apiClient);
        SettingsDialogShower?.Invoke(settingsForm);
    }

    /// <summary>
    /// Open About Developer dialog.
    /// </summary>
    public void LaunchAbout()
    {
        using var aboutForm = new AboutForm();
        AboutDialogShower?.Invoke(aboutForm);
    }

    /// <summary>
    /// Check whether onboarding is required based on explicit flag or config file presence.
    /// </summary>
    public bool IsOnboardingRequired()
    {
        if (OnboardingComplete)
        {
            return false;
        }

        if (File.Exists(ConfigFilePath))
        {
            return false;
        }

        return true;
    }

    /// <summary>
    /// Display SetupWizardDialog modally within the context of the main dashboard.
    /// </summary>
    public DialogResult LaunchSetupWizard()
    {
        using var wizard = new SetupWizardDialog(_apiClient);
        var result = wizard.ShowDialog(this);
        if (result == DialogResult.OK)
        {
            OnboardingComplete = true;
            _ = RefreshStatusAsync();
        }
        return result;
    }

    protected override void Dispose(bool disposing)
    {
        if (disposing)
        {
            PollingTimer?.Stop();
            PollingTimer?.Dispose();
        }
        base.Dispose(disposing);
    }
}
