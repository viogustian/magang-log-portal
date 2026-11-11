using System.Drawing;
using System.Windows.Forms;
using MagangLog.Desktop.Models;
using MagangLog.Desktop.Services;

namespace MagangLog.Desktop.Controls;

/// <summary>
/// Panel for Step 5 of the onboarding wizard allowing interns to configure the daily logbook
/// submission mode (Review Dulu, Full Access, or Notifikasi Saja), enforce Full Access safety gate,
/// and authenticate session with Monev MagangHub Kemnaker portal.
/// </summary>
public class SubmissionModePanel : Panel
{
    private readonly BackendApiClient _apiClient;
    private readonly RadioButton _rdoReview;
    private readonly RadioButton _rdoAuto;
    private readonly RadioButton _rdoNotify;
    private bool _isUpdatingRadio = false;

    private readonly Panel _pnlFullAccessWarning;
    private readonly CheckBox _chkFullAccessConfirm;
    private readonly PortalAuthPanel _portalAuthPanel;

    public RadioButton RadioReview => _rdoReview;
    public RadioButton RadioAuto => _rdoAuto;
    public RadioButton RadioNotify => _rdoNotify;
    public Label PortalStatusLabel => _portalAuthPanel.StatusLabel;
    public Button OpenLoginButton => _portalAuthPanel.OpenLoginButton;
    public Button ConfirmLoginButton => _portalAuthPanel.ConfirmLoginButton;
    public Button RefreshPortalButton => _portalAuthPanel.RefreshStatusButton;
    public bool IsPortalAuthenticated => _portalAuthPanel.IsAuthenticated;

    public event EventHandler? ModeChanged;

    public string ReviewMode
    {
        get
        {
            if (_rdoAuto.Checked) return "auto";
            if (_rdoNotify.Checked) return "notify";
            return "review";
        }
        set => SetMode(value);
    }

    public bool FullAccessConfirmed
    {
        get => _chkFullAccessConfirm.Checked;
        set
        {
            _chkFullAccessConfirm.Checked = value;
            ModeChanged?.Invoke(this, EventArgs.Empty);
        }
    }

    public bool IsGateSatisfied => ReviewMode != "auto" || FullAccessConfirmed;

    public bool IsFullAccessWarningVisible => _pnlFullAccessWarning.Visible;

    public SubmissionModePanel(BackendApiClient? apiClient = null)
    {
        _apiClient = apiClient ?? new BackendApiClient();

        Dock = DockStyle.Fill;
        BackColor = Color.White;
        Padding = new Padding(8);
        AutoScroll = true;

        // Top prompt label
        var lblTitle = new Label
        {
            Text = "Pilih Mode Pengiriman Logbook ke Portal Monev Kemnaker:",
            Dock = DockStyle.Top,
            Height = 24,
            Font = new Font(Font.FontFamily, 9.5f, FontStyle.Bold),
            ForeColor = Color.FromArgb(30, 41, 59)
        };

        // Options panel
        var optionsPanel = new Panel
        {
            Dock = DockStyle.Top,
            Height = 175,
            Padding = new Padding(4, 4, 4, 8)
        };

        var reviewCard = CreateOptionCard(
            out _rdoReview,
            "Review Dulu (Direkomendasikan)",
            "AI menyusun draf logbook harian, Anda meninjau dan menyetujuinya di dashboard sebelum dikirim ke portal Monev Kemnaker.",
            0);
        _rdoReview.Checked = true;
        _rdoReview.CheckedChanged += (_, _) =>
        {
            if (_rdoReview.Checked) SelectMode(_rdoReview);
        };

        var autoCard = CreateOptionCard(
            out _rdoAuto,
            "Full Access (Otomatis Kirim)",
            "AI menyusun draf dan langsung mengirimkannya secara otomatis ke portal Monev Kemnaker tanpa konfirmasi manual.",
            56);
        _rdoAuto.CheckedChanged += (_, _) =>
        {
            if (_rdoAuto.Checked) SelectMode(_rdoAuto);
        };

        var notifyCard = CreateOptionCard(
            out _rdoNotify,
            "Notifikasi Saja",
            "AI menyusun draf logbook secara lokal dan mengirimkan notifikasi pengingat, namun portal submission tidak dijalankan secara otomatis.",
            112);
        _rdoNotify.CheckedChanged += (_, _) =>
        {
            if (_rdoNotify.Checked) SelectMode(_rdoNotify);
        };

        optionsPanel.Controls.Add(notifyCard);
        optionsPanel.Controls.Add(autoCard);
        optionsPanel.Controls.Add(reviewCard);

        // --- Safety Warning Panel for Full Access ---
        _pnlFullAccessWarning = new Panel
        {
            Dock = DockStyle.Top,
            Height = 110,
            Visible = false,
            BackColor = Color.FromArgb(254, 242, 242),
            BorderStyle = BorderStyle.FixedSingle,
            Padding = new Padding(12, 10, 12, 10)
        };

        var lblWarningTitle = new Label
        {
            Text = "⚠️ Peringatan Keamanan Mode Full Access",
            Dock = DockStyle.Top,
            Height = 20,
            Font = new Font(Font.FontFamily, 9f, FontStyle.Bold),
            ForeColor = Color.FromArgb(185, 28, 28)
        };

        var lblWarningDesc = new Label
        {
            Text = "Draf logbook harian yang dibuat AI akan langsung dikirim ke portal Kemnaker atas nama Anda. Data yang dikirim meliputi: ringkasan harian, berkas proyek terkait, dan log commit Git.",
            Dock = DockStyle.Top,
            Height = 36,
            Font = new Font(Font.FontFamily, 8f, FontStyle.Regular),
            ForeColor = Color.FromArgb(153, 27, 27)
        };

        _chkFullAccessConfirm = new CheckBox
        {
            Text = "Saya memahami dan menyetujui pengiriman log harian secara otomatis ke portal",
            Dock = DockStyle.Top,
            Height = 24,
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Bold),
            ForeColor = Color.FromArgb(153, 27, 27),
            Checked = false
        };
        _chkFullAccessConfirm.CheckedChanged += (_, _) => ModeChanged?.Invoke(this, EventArgs.Empty);

        _pnlFullAccessWarning.Controls.Add(_chkFullAccessConfirm);
        _pnlFullAccessWarning.Controls.Add(lblWarningDesc);
        _pnlFullAccessWarning.Controls.Add(lblWarningTitle);

        // --- Portal Authentication Section ---
        _portalAuthPanel = new PortalAuthPanel(
            _apiClient,
            groupTitle: "Sesi Autentikasi Portal Monev MagangHub Kemnaker",
            panelHeight: 152)
        {
            Margin = new Padding(0, 8, 0, 8)
        };

        // --- Notification Banner ---
        var notificationBanner = new Panel
        {
            Dock = DockStyle.Top,
            Height = 48,
            BackColor = Color.FromArgb(241, 245, 249),
            Padding = new Padding(12, 10, 12, 10),
            Margin = new Padding(0, 8, 0, 0)
        };

        var lblNotification = new Label
        {
            Text = "🔔 Notifikasi pengingat tetap aktif di semua mode. Jadwal dan saluran notifikasi (toast/desktop) dapat disesuaikan di pengaturan dashboard kapan saja.",
            Dock = DockStyle.Fill,
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Regular),
            ForeColor = Color.FromArgb(51, 65, 85),
            TextAlign = ContentAlignment.MiddleLeft
        };
        notificationBanner.Controls.Add(lblNotification);

        // Spacer panel between warning and banner
        var spacer = new Panel
        {
            Dock = DockStyle.Top,
            Height = 8
        };

        // Assemble controls (Dock order)
        Controls.Add(notificationBanner);
        Controls.Add(spacer);
        Controls.Add(_portalAuthPanel);
        Controls.Add(_pnlFullAccessWarning);
        Controls.Add(optionsPanel);
        Controls.Add(lblTitle);
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

        panel.Cursor = Cursors.Hand;
        lblDesc.Cursor = Cursors.Hand;
        var rdoLocal = rdo;
        panel.Click += (_, _) => SelectMode(rdoLocal);
        lblDesc.Click += (_, _) => SelectMode(rdoLocal);

        panel.Controls.Add(lblDesc);
        panel.Controls.Add(rdo);
        return panel;
    }

    public void SelectMode(RadioButton selected)
    {
        if (_isUpdatingRadio) return;
        _isUpdatingRadio = true;
        try
        {
            _rdoReview.Checked = (selected == _rdoReview);
            _rdoAuto.Checked = (selected == _rdoAuto);
            _rdoNotify.Checked = (selected == _rdoNotify);
        }
        finally
        {
            _isUpdatingRadio = false;
        }
        HandleModeSelectionChanged();
    }

    public void SetMode(string mode, bool confirmed = false)
    {
        var clean = mode?.Trim().ToLowerInvariant();
        if (clean == "auto")
        {
            SelectMode(_rdoAuto);
            _chkFullAccessConfirm.Checked = confirmed;
        }
        else if (clean == "notify")
        {
            SelectMode(_rdoNotify);
            _chkFullAccessConfirm.Checked = false;
        }
        else
        {
            SelectMode(_rdoReview);
            _chkFullAccessConfirm.Checked = false;
        }
    }

    private void HandleModeSelectionChanged()
    {
        _pnlFullAccessWarning.Visible = _rdoAuto.Checked;
        ModeChanged?.Invoke(this, EventArgs.Empty);
    }

    /// <summary>
    /// Checks session status from backend and updates portal indicator label.
    /// </summary>
    public Task RefreshAuthStatusAsync() => _portalAuthPanel.RefreshAuthStatusAsync();

    /// <summary>
    /// Launches interactive login browser for portal Monev Kemnaker.
    /// </summary>
    public Task OpenPortalLoginAsync() => _portalAuthPanel.OpenPortalLoginAsync();

    /// <summary>
    /// Asks the backend to confirm and capture the active portal login session immediately.
    /// </summary>
    public Task ConfirmPortalLoginAsync() => _portalAuthPanel.ConfirmPortalLoginAsync();
}

