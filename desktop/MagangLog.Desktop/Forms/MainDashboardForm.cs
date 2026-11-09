using MagangLog.Desktop.Services;

namespace MagangLog.Desktop.Forms;

/// <summary>
/// Main desktop dashboard window for monitoring, review, calendar, and settings.
/// Launches SetupWizardDialog modally on load when onboarding has not been completed.
/// </summary>
public class MainDashboardForm : Form
{
    private readonly BackendApiClient _apiClient;
    private readonly Label _lblTitle;
    private readonly Label _lblStatus;
    private readonly Button _btnOpenWizard;

    public bool OnboardingComplete { get; set; } = false;
    public string ConfigFilePath { get; set; } = "config/config.yaml";

    public MainDashboardForm(BackendApiClient? apiClient = null)
    {
        _apiClient = apiClient ?? new BackendApiClient();

        Text = "Local Dashboard — Magang Log";
        StartPosition = FormStartPosition.CenterScreen;
        Size = new Size(1024, 720);
        MinimumSize = new Size(800, 600);
        BackColor = Color.FromArgb(248, 250, 252);

        var headerPanel = new Panel
        {
            Dock = DockStyle.Top,
            Height = 64,
            BackColor = Color.White,
            Padding = new Padding(24, 16, 24, 16)
        };

        _lblTitle = new Label
        {
            Text = "Magang Log — Local Dashboard",
            Font = new Font(Font.FontFamily, 13f, FontStyle.Bold),
            ForeColor = Color.FromArgb(15, 23, 42),
            Dock = DockStyle.Left,
            AutoSize = true
        };

        _btnOpenWizard = new Button
        {
            Text = "Buka Setup Wizard",
            Dock = DockStyle.Right,
            Width = 150,
            Height = 32,
            BackColor = Color.FromArgb(241, 245, 249),
            ForeColor = Color.FromArgb(30, 41, 59),
            FlatStyle = FlatStyle.Flat,
            Cursor = Cursors.Hand
        };
        _btnOpenWizard.Click += (_, _) => LaunchSetupWizard();

        headerPanel.Controls.Add(_lblTitle);
        headerPanel.Controls.Add(_btnOpenWizard);
        Controls.Add(headerPanel);

        var bodyPanel = new Panel
        {
            Dock = DockStyle.Fill,
            Padding = new Padding(24)
        };

        _lblStatus = new Label
        {
            Text = "Dashboard siap digunakan.",
            Dock = DockStyle.Top,
            Font = new Font(Font.FontFamily, 10.5f, FontStyle.Regular),
            ForeColor = Color.FromArgb(71, 85, 105),
            Height = 40
        };

        bodyPanel.Controls.Add(_lblStatus);
        Controls.Add(bodyPanel);
    }

    protected override void OnLoad(EventArgs e)
    {
        base.OnLoad(e);

        if (IsOnboardingRequired())
        {
            LaunchSetupWizard();
        }
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

        // If config file already exists and is non-empty, onboarding was completed
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
            _lblStatus.Text = "Onboarding selesai. Konfigurasi berhasil disimpan.";
        }
        return result;
    }
}

