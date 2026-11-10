using MagangLog.Desktop.Controls;
using MagangLog.Desktop.Models;
using MagangLog.Desktop.Services;

namespace MagangLog.Desktop.Forms;

/// <summary>
/// Modal 6-step guided onboarding dialog for system requirements, project folders,
/// WorkProfile detection, Git intensity, review mode, and configuration summary.
/// </summary>
public class SetupWizardDialog : Form
{
    private readonly BackendApiClient _apiClient;
    private readonly StepIndicatorPanel _indicator;
    private readonly Panel _contentContainer;
    private readonly Panel[] _stepPanels;
    private readonly GeminiCredentialsCard _geminiCard;
    private readonly RequirementListPanel _requirementPanel;
    private readonly FolderListPanel _folderPanel;
    private readonly JobRolePanel _rolePanel;
    private readonly GitFrequencyPanel _frequencyPanel;
    private readonly SubmissionModePanel _submissionModePanel;
    private readonly SummaryPanel _summaryPanel;
    private readonly Button _btnBack;
    private readonly Button _btnNext;
    private readonly Label _lblStatus;

    private int _currentStep = 0;
    private int? _returnStep = null;

    public int StepCount => 6;
    public int CurrentStep => _currentStep;
    public WizardProgressState State { get; private set; } = new();

    public Button BackButton => _btnBack;
    public Button NextButton => _btnNext;
    public Label StatusLabel => _lblStatus;
    public StepIndicatorPanel StepIndicator => _indicator;
    public GeminiCredentialsCard GeminiCard => _geminiCard;
    public string GeminiApiKey
    {
        get => _geminiCard.ApiKey;
        set => _geminiCard.ApiKey = value;
    }
    public RequirementListPanel RequirementPanel => _requirementPanel;
    public FolderListPanel FolderPanel => _folderPanel;
    public JobRolePanel RolePanel => _rolePanel;
    public GitFrequencyPanel FrequencyPanel => _frequencyPanel;
    public SubmissionModePanel SubmissionModePanel => _submissionModePanel;
    public SummaryPanel SummaryPanel => _summaryPanel;
    public IReadOnlyList<Panel> StepPanels => _stepPanels;

    public SetupWizardDialog(BackendApiClient? apiClient = null)
    {
        _apiClient = apiClient ?? new BackendApiClient();

        Text = "Setup Wizard — Magang Log";
        StartPosition = FormStartPosition.CenterParent;
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = false;
        MinimizeBox = false;
        ShowInTaskbar = false;
        Size = new Size(760, 620);
        MinimumSize = new Size(720, 560);
        BackColor = Color.White;

        // Top: Step Indicator Panel
        _indicator = new StepIndicatorPanel();
        Controls.Add(_indicator);

        // Bottom: Navigation Panel
        var navPanel = new Panel
        {
            Dock = DockStyle.Bottom,
            Height = 64,
            BackColor = Color.FromArgb(248, 250, 252),
            Padding = new Padding(20, 14, 20, 14)
        };

        _lblStatus = new Label
        {
            Dock = DockStyle.Left,
            AutoSize = false,
            Width = 420,
            TextAlign = ContentAlignment.MiddleLeft,
            ForeColor = Color.FromArgb(100, 116, 139),
            Font = new Font(Font.FontFamily, 9f, FontStyle.Regular)
        };

        _btnNext = new Button
        {
            Text = "Lanjut",
            Dock = DockStyle.Right,
            Width = 110,
            Height = 36,
            BackColor = Color.FromArgb(37, 99, 235),
            ForeColor = Color.White,
            FlatStyle = FlatStyle.Flat,
            Font = new Font(Font.FontFamily, 9.5f, FontStyle.Bold),
            Cursor = Cursors.Hand
        };
        _btnNext.FlatAppearance.BorderSize = 0;
        _btnNext.Click += async (_, _) => await HandleNextClickAsync();

        _btnBack = new Button
        {
            Text = "Kembali",
            Dock = DockStyle.Right,
            Width = 100,
            Height = 36,
            BackColor = Color.FromArgb(241, 245, 249),
            ForeColor = Color.FromArgb(71, 85, 105),
            FlatStyle = FlatStyle.Flat,
            Font = new Font(Font.FontFamily, 9.5f, FontStyle.Regular),
            Cursor = Cursors.Hand,
            Enabled = false
        };
        _btnBack.FlatAppearance.BorderSize = 0;
        _btnBack.Click += (_, _) => NavigateBack();

        navPanel.Controls.Add(_lblStatus);
        navPanel.Controls.Add(_btnBack);
        navPanel.Controls.Add(_btnNext);
        Controls.Add(navPanel);

        // Center: Content Container managing 6 step panels
        _contentContainer = new Panel
        {
            Dock = DockStyle.Fill,
            BackColor = Color.White,
            Padding = new Padding(24, 16, 24, 16)
        };

        _stepPanels = new Panel[StepCount];
        for (int i = 0; i < StepCount; i++)
        {
            var pnl = CreateStepPlaceholderPanel(i);
            _stepPanels[i] = pnl;
            _contentContainer.Controls.Add(pnl);
        }

        // Initialize and host GeminiCredentialsCard and RequirementListPanel in Step 0
        _geminiCard = new GeminiCredentialsCard(_apiClient);
        _geminiCard.Dock = DockStyle.Top;
        _geminiCard.GateStateChanged += (_, _) => EvaluateGateState();

        _requirementPanel = new RequirementListPanel(_apiClient);
        _requirementPanel.Dock = DockStyle.Fill;
        _requirementPanel.GateStateChanged += (_, _) => EvaluateGateState();

        _stepPanels[0].Controls.Add(_requirementPanel);
        _stepPanels[0].Controls.Add(_geminiCard);
        _geminiCard.BringToFront();

        // Initialize and host FolderListPanel in Step 1
        _folderPanel = new FolderListPanel(_apiClient);
        _folderPanel.GateStateChanged += (_, _) => EvaluateGateState();
        _stepPanels[1].Controls.Add(_folderPanel);
        _folderPanel.BringToFront();

        // Initialize and host JobRolePanel in Step 2
        _rolePanel = new JobRolePanel(_apiClient);
        _rolePanel.ApiKeyProvider = () => !string.IsNullOrEmpty(State.GeminiApiKey) ? State.GeminiApiKey : _geminiCard.ApiKey;
        _rolePanel.GateStateChanged += (_, _) => EvaluateGateState();
        _stepPanels[2].Controls.Add(_rolePanel);
        _rolePanel.BringToFront();

        // Initialize and host GitFrequencyPanel in Step 3
        _frequencyPanel = new GitFrequencyPanel();
        _frequencyPanel.SourcesChanged += (_, _) => EvaluateGateState();
        _stepPanels[3].Controls.Add(_frequencyPanel);
        _frequencyPanel.BringToFront();

        // Initialize and host SubmissionModePanel in Step 4
        _submissionModePanel = new SubmissionModePanel(_apiClient);
        _submissionModePanel.ModeChanged += (_, _) => EvaluateGateState();
        _stepPanels[4].Controls.Add(_submissionModePanel);
        _submissionModePanel.BringToFront();

        // Initialize and host SummaryPanel in Step 5
        _summaryPanel = new SummaryPanel();
        _summaryPanel.EditSectionRequested += (_, targetStep) => HandleEditSection(targetStep);
        _stepPanels[5].Controls.Add(_summaryPanel);
        _summaryPanel.BringToFront();

        Controls.Add(_contentContainer);

        // Activate step 0
        GoToStep(0);
    }

    protected override async void OnLoad(EventArgs e)
    {
        base.OnLoad(e);
        await LoadProgressAsync();
        _ = _rolePanel.LoadPresetsAsync();
        if (_currentStep == 0)
        {
            await _geminiCard.LoadSavedKeyAsync();
            await _requirementPanel.LoadRequirementsAsync();
        }
    }

    protected override async void OnFormClosing(FormClosingEventArgs e)
    {
        base.OnFormClosing(e);

        // If closed prematurely without finishing, persist entered inputs to disk
        if (DialogResult != DialogResult.OK)
        {
            try
            {
                State.CurrentStep = _currentStep;
                await _apiClient.SaveWizardProgressAsync(State);
            }
            catch
            {
                // Suppress background errors during closing
            }
        }
    }

    /// <summary>
    /// Loads saved wizard progress from the backend and resumes at the appropriate step.
    /// </summary>
    public async Task LoadProgressAsync()
    {
        try
        {
            var saved = await _apiClient.GetWizardProgressAsync();
            if (saved != null && (saved.CurrentStep > 0 || saved.CompletedSteps.Count > 0 || saved.StepData.Count > 0))
            {
                ApplyProgressState(saved);
            }
        }
        catch
        {
            // Fallback to initial step if backend is unreachable
        }
    }

    /// <summary>
    /// Applies progress state and activates the corresponding step panel.
    /// </summary>
    public void ApplyProgressState(WizardProgressState state)
    {
        State = state;
        if (!string.IsNullOrEmpty(state.GeminiApiKey))
        {
            _geminiCard.ApiKey = state.GeminiApiKey;
        }
        if (!string.IsNullOrEmpty(state.GeminiModel))
        {
            _geminiCard.SelectedModel = state.GeminiModel;
        }

        if (state.ProjectFolders != null && state.ProjectFolders.Count > 0)
        {
            _ = _folderPanel.LoadFoldersAsync(state.ProjectFolders);
        }

        if (!string.IsNullOrEmpty(state.ProfileName) || (state.Keywords != null && state.Keywords.Count > 0))
        {
            _rolePanel.Description = state.RoleDescription;
            _rolePanel.KeywordPanel.SetProfile(state.ProfileName, state.Keywords ?? new List<string>());
        }

        if (state.Sources != null)
        {
            _frequencyPanel.SetConfig(state.Sources);
        }

        if (!string.IsNullOrEmpty(state.ReviewMode))
        {
            _submissionModePanel.SetMode(state.ReviewMode, state.FullAccessConfirmed);
        }

        var stepToActivate = Math.Clamp(state.CurrentStep, 0, StepCount - 1);
        GoToStep(stepToActivate);
    }

    private void HandleEditSection(int targetStep)
    {
        _returnStep = 5;
        GoToStep(targetStep);
    }

    /// <summary>
    /// Switch active panel and update navigation buttons and step indicator.
    /// </summary>
    public void GoToStep(int stepIndex)
    {
        _currentStep = Math.Clamp(stepIndex, 0, StepCount - 1);

        for (int i = 0; i < _stepPanels.Length; i++)
        {
            _stepPanels[i].Visible = (i == _currentStep);
        }

        _btnBack.Enabled = (_currentStep > 0);
        _btnNext.Text = (_currentStep == StepCount - 1) ? "Selesai" : "Lanjut";

        _indicator.UpdateStep(_currentStep, State.CompletedSteps);

        if (_currentStep == 4)
        {
            _ = _submissionModePanel.RefreshAuthStatusAsync();
        }
        else if (_currentStep == 5)
        {
            _summaryPanel.RefreshSummary(State);
        }

        EvaluateGateState();
    }

    /// <summary>
    /// Evaluates step-specific gates (e.g. Requirement gate on step 0, Folder gate on step 1).
    /// </summary>
    public void EvaluateGateState()
    {
        if (_currentStep == 0)
        {
            var reqsSatisfied = _requirementPanel == null || _requirementPanel.AllRequirementsSatisfied;
            var keyProvided = _geminiCard == null || _geminiCard.IsKeyProvided;

            if (reqsSatisfied && keyProvided)
            {
                _btnNext.Enabled = true;
                _lblStatus.Text = "Semua requirement sistem & Kunci Gemini AI siap.";
                _lblStatus.ForeColor = Color.FromArgb(22, 101, 52);
            }
            else if (!reqsSatisfied)
            {
                _btnNext.Enabled = false;
                var count = _requirementPanel?.UnmetCount ?? 0;
                _lblStatus.Text = $"{count} requirement belum terpenuhi — lihat item bertanda ❌/⚠️ di bawah";
                _lblStatus.ForeColor = Color.FromArgb(220, 38, 38);
            }
            else
            {
                _btnNext.Enabled = false;
                _lblStatus.Text = "Wajib memasukkan Google AI Studio API Key untuk melanjutkan.";
                _lblStatus.ForeColor = Color.FromArgb(220, 38, 38);
            }
        }
        else if (_currentStep == 1)
        {
            if (_folderPanel == null || _folderPanel.HasValidFolders)
            {
                _btnNext.Enabled = true;
                var count = _folderPanel?.ValidFolderCount ?? 0;
                _lblStatus.Text = $"{count} folder proyek valid terdaftar.";
                _lblStatus.ForeColor = Color.FromArgb(22, 101, 52);
            }
            else
            {
                _btnNext.Enabled = false;
                _lblStatus.Text = "Pilih minimal satu folder proyek yang valid untuk melanjutkan.";
                _lblStatus.ForeColor = Color.FromArgb(220, 38, 38);
            }
        }
        else if (_currentStep == 2)
        {
            if (_rolePanel == null || _rolePanel.HasValidProfile)
            {
                _btnNext.Enabled = true;
                var count = _rolePanel?.KeywordPanel.Keywords.Count ?? 0;
                _lblStatus.Text = $"Profil '{_rolePanel?.KeywordPanel.ProfileName}' siap ({count} kata kunci).";
                _lblStatus.ForeColor = Color.FromArgb(22, 101, 52);
            }
            else
            {
                _btnNext.Enabled = false;
                _lblStatus.Text = "Masukkan nama profil dan minimal satu kata kunci aplikasi untuk melanjutkan.";
                _lblStatus.ForeColor = Color.FromArgb(220, 38, 38);
            }
        }
        else if (_currentStep == 3)
        {
            if (_frequencyPanel == null || _frequencyPanel.HasActiveSources)
            {
                _btnNext.Enabled = true;
                _lblStatus.Text = "Pilihan frekuensi Git dan persetujuan privasi siap.";
                _lblStatus.ForeColor = Color.FromArgb(22, 101, 52);
            }
            else
            {
                _btnNext.Enabled = false;
                _lblStatus.Text = "Aktifkan minimal satu sumber bukti (Git, Aplikasi, atau Browser) untuk melanjutkan.";
                _lblStatus.ForeColor = Color.FromArgb(220, 38, 38);
            }
        }
        else if (_currentStep == 4)
        {
            if (_submissionModePanel == null || _submissionModePanel.IsGateSatisfied)
            {
                _btnNext.Enabled = true;
                var modeName = _submissionModePanel?.ReviewMode switch
                {
                    "auto" => "Full Access (Otomatis)",
                    "notify" => "Notifikasi Saja",
                    _ => "Review Dulu"
                };
                _lblStatus.Text = $"Mode pengiriman '{modeName}' siap.";
                _lblStatus.ForeColor = Color.FromArgb(22, 101, 52);
            }
            else
            {
                _btnNext.Enabled = false;
                _lblStatus.Text = "Centang konfirmasi persetujuan keamanan Full Access untuk melanjutkan.";
                _lblStatus.ForeColor = Color.FromArgb(220, 38, 38);
            }
        }
        else if (_currentStep == 5)
        {
            _btnNext.Enabled = true;
            _lblStatus.Text = "Semua konfigurasi siap disimpan. Klik Selesai untuk mulai menggunakan Magang Log.";
            _lblStatus.ForeColor = Color.FromArgb(22, 101, 52);
        }
        else
        {
            _btnNext.Enabled = true;
            _lblStatus.Text = string.Empty;
        }
    }

    /// <summary>
    /// Move backward to the previous step.
    /// </summary>
    public void NavigateBack()
    {
        if (_currentStep > 0)
        {
            GoToStep(_currentStep - 1);
        }
    }

    /// <summary>
    /// Advance to the next step, mark previous completed, and save state.
    /// </summary>
    public async Task HandleNextClickAsync()
    {
        if (_currentStep == 0)
        {
            if (_geminiCard != null)
            {
                State.GeminiApiKey = _geminiCard.ApiKey;
                State.GeminiModel = _geminiCard.SelectedModel;
                State.SetStepData("gemini_api_key", State.GeminiApiKey);
                State.SetStepData("gemini_model", State.GeminiModel);
            }
        }
        else if (_currentStep == 1)
        {
            State.ProjectFolders = _folderPanel.GetValidFolderPaths();
            State.SetStepData("project_folders", State.ProjectFolders);
        }
        else if (_currentStep == 2)
        {
            State.RoleDescription = _rolePanel.Description;
            State.ProfileName = _rolePanel.KeywordPanel.ProfileName;
            State.Keywords = _rolePanel.KeywordPanel.Keywords.ToList();
            State.SetStepData("role_description", State.RoleDescription);
            State.SetStepData("profile_name", State.ProfileName);
            State.SetStepData("keywords", State.Keywords);
        }
        else if (_currentStep == 3)
        {
            State.Sources = _frequencyPanel.GetConfig();
            State.SetStepData("sources", State.Sources);
        }
        else if (_currentStep == 4)
        {
            State.ReviewMode = _submissionModePanel.ReviewMode;
            State.FullAccessConfirmed = _submissionModePanel.FullAccessConfirmed;
            State.SetStepData("review_mode", State.ReviewMode);
            State.SetStepData("full_access_confirmed", State.FullAccessConfirmed);
        }

        // If returned from a quick-edit "Ubah" jump, route back directly to Step 6 (index 5)
        if (_returnStep.HasValue)
        {
            var dest = _returnStep.Value;
            _returnStep = null;
            GoToStep(dest);
            return;
        }

        if (_currentStep >= StepCount - 1)
        {
            // Final step: persist complete configuration to disk via backend API
            _btnNext.Enabled = false;
            _btnNext.Text = "⏳ Menyimpan...";
            try
            {
                var appConfigs = new List<ApplicationConfig>();
                if (State.Keywords != null && State.Keywords.Count > 0)
                {
                    appConfigs.Add(new ApplicationConfig
                    {
                        Name = string.IsNullOrWhiteSpace(State.ProfileName) ? "General" : State.ProfileName,
                        ProcessNames = State.Keywords.Where(k => k.EndsWith(".exe", StringComparison.OrdinalIgnoreCase)).ToList(),
                        FileExtensions = new List<string>()
                    });
                }

                var workProfile = new WorkProfile
                {
                    ProfileName = string.IsNullOrWhiteSpace(State.ProfileName) ? "General Intern" : State.ProfileName,
                    NaturalDescription = State.RoleDescription,
                    Applications = appConfigs,
                    WatchFolders = State.ProjectFolders ?? new List<string>(),
                    BrowserDomains = new List<string> { "github.com", "gitlab.com", "stackoverflow.com" }
                };

                var saveReq = new SaveConfigRequest
                {
                    Timezone = "Asia/Jakarta",
                    Workdays = new List<string> { "mon", "tue", "wed", "thu", "fri" },
                    Review = new ReviewSettingsDto
                    {
                        Mode = State.ReviewMode,
                        AutoIfConfident = false
                    },
                    Sources = new SourcesSettingsDto
                    {
                        Git = new GitSourceSettingsDto
                        {
                            Enabled = State.Sources?.GitEnabled ?? true,
                            Repositories = State.ProjectFolders ?? new List<string>()
                        },
                        App = new AppSourceSettingsDto
                        {
                            Enabled = State.Sources?.AppEnabled ?? true,
                            WorkProfile = workProfile
                        },
                        Browser = new BrowserSourceSettingsDto
                        {
                            Enabled = State.Sources?.BrowserEnabled ?? false,
                            AllowDomains = new List<string> { "github.com", "gitlab.com", "stackoverflow.com" }
                        }
                    },
                    WorkProfile = workProfile,
                    Llm = new LlmSettingsDto
                    {
                        Provider = "gemini",
                        ApiKey = State.GeminiApiKey,
                        Model = State.GeminiModel
                    }
                };

                await _apiClient.SaveConfigAsync(saveReq);

                State.MarkStepCompleted(_currentStep);
                DialogResult = DialogResult.OK;
                Close();
                return;
            }
            catch (Exception ex)
            {
                _btnNext.Enabled = true;
                _btnNext.Text = "Selesai";
                _lblStatus.Text = $"Gagal menyimpan konfigurasi: {ex.Message}";
                _lblStatus.ForeColor = Color.FromArgb(220, 38, 38);
                return;
            }
        }

        // Mark current step as completed
        State.MarkStepCompleted(_currentStep);
        var nextStep = _currentStep + 1;
        State.CurrentStep = nextStep;

        GoToStep(nextStep);

        // Asynchronously persist progress
        try
        {
            await _apiClient.SaveWizardProgressAsync(State);
        }
        catch (Exception ex)
        {
            _lblStatus.Text = $"Peringatan simpan progres: {ex.Message}";
        }
    }

    private Panel CreateStepPlaceholderPanel(int stepIndex)
    {
        var panel = new Panel
        {
            Dock = DockStyle.Fill,
            Visible = false
        };

        var titles = new[]
        {
            "Langkah 1: Cek Requirement Sistem (Gate)",
            "Langkah 2: Folder Proyek",
            "Langkah 3: Pekerjaan dan Kata Kunci Aplikasi",
            "Langkah 4: Seberapa Sering Pakai Git",
            "Langkah 5: Mode Pengiriman Log",
            "Langkah 6: Ringkasan dan Konfirmasi"
        };

        var subtitles = new[]
        {
            "Sistem memvalidasi dependensi runtime yang dibutuhkan (Python, Playwright, dll).",
            "Pilih satu atau beberapa direktori proyek untuk pemantauan aktivitas.",
            "Ceritakan peran harian Anda atau gunakan kata kunci deteksi aplikasi desktop.",
            "Tentukan intensitas penggunaan Git untuk mengatur bobot sumber data bukti.",
            "Pilih mode persetujuan dan pengiriman draf logbook ke portal Monev Kemnaker.",
            "Tinjau kembali seluruh pilihan konfigurasi sebelum menyelesaikan penyiapan."
        };

        var header = new Label
        {
            Text = titles[stepIndex],
            Font = new Font(Font.FontFamily, 13f, FontStyle.Bold),
            ForeColor = Color.FromArgb(15, 23, 42),
            Dock = DockStyle.Top,
            Height = 32
        };

        var subHeader = new Label
        {
            Text = subtitles[stepIndex],
            Font = new Font(Font.FontFamily, 9.5f, FontStyle.Regular),
            ForeColor = Color.FromArgb(100, 116, 139),
            Dock = DockStyle.Top,
            Height = 26
        };

        panel.Controls.Add(subHeader);
        panel.Controls.Add(header);
        return panel;
    }
}

