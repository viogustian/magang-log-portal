using System.Drawing;
using System.Windows.Forms;
using MagangLog.Desktop.Services;

namespace MagangLog.Desktop.Controls;

/// <summary>
/// Shared portal authentication GroupBox control used by Setup Wizard and Settings.
/// Provides non-blocking login launch, live status polling, and an explicit confirmation button.
/// </summary>
public class PortalAuthPanel : Panel
{
    private readonly BackendApiClient _apiClient;
    private readonly GroupBox _grpPortal;
    private readonly Label _lblStatus;
    private readonly Button _btnOpenLogin;
    private readonly Button _btnConfirmLogin;
    private readonly Button _btnRefreshStatus;
    private readonly System.Windows.Forms.Timer _pollTimer;
    private bool _isLoginRunning;
    private bool _isPollingTick;

    public Label StatusLabel => _lblStatus;
    public Button OpenLoginButton => _btnOpenLogin;
    public Button ConfirmLoginButton => _btnConfirmLogin;
    public Button RefreshStatusButton => _btnRefreshStatus;
    public bool IsAuthenticated { get; private set; }

    public PortalAuthPanel(
        BackendApiClient apiClient,
        string groupTitle = "Sesi Autentikasi Portal Monev MagangHub Kemnaker",
        int panelHeight = 152,
        Color? cardBackColor = null)
    {
        _apiClient = apiClient ?? throw new ArgumentNullException(nameof(apiClient));

        Dock = DockStyle.Top;
        Height = panelHeight;
        BackColor = Color.Transparent;

        _grpPortal = new GroupBox
        {
            Text = groupTitle,
            Dock = DockStyle.Fill,
            Font = new Font(Font.FontFamily, 9f, FontStyle.Bold),
            ForeColor = Color.FromArgb(30, 41, 59),
            BackColor = cardBackColor ?? Color.FromArgb(248, 250, 252),
            Padding = new Padding(12, 8, 12, 8)
        };

        _lblStatus = new Label
        {
            Text = "⚪ Status Sesi: Belum login / memeriksa sesi...",
            Location = new Point(14, 24),
            Size = new Size(640, 22),
            Font = new Font(Font.FontFamily, 9f, FontStyle.Bold),
            ForeColor = Color.FromArgb(71, 85, 105),
            AutoEllipsis = true
        };

        _btnOpenLogin = new Button
        {
            Text = "🌐 Buka Browser Login",
            Location = new Point(14, 50),
            Size = new Size(185, 32),
            BackColor = Color.FromArgb(16, 185, 129),
            ForeColor = Color.White,
            FlatStyle = FlatStyle.Flat,
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Bold),
            Cursor = Cursors.Hand
        };
        _btnOpenLogin.FlatAppearance.BorderSize = 0;
        _btnOpenLogin.Click += async (_, _) => await OpenPortalLoginAsync();

        _btnConfirmLogin = new Button
        {
            Text = "✅ Sudah Selesai Login",
            Location = new Point(207, 50),
            Size = new Size(195, 32),
            BackColor = Color.FromArgb(226, 232, 240),
            ForeColor = Color.FromArgb(71, 85, 105),
            FlatStyle = FlatStyle.Flat,
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Bold),
            Cursor = Cursors.Hand,
            Enabled = false
        };
        _btnConfirmLogin.FlatAppearance.BorderSize = 0;
        _btnConfirmLogin.Click += async (_, _) => await ConfirmPortalLoginAsync();

        _btnRefreshStatus = new Button
        {
            Text = "🔄 Cek Status",
            Location = new Point(410, 50),
            Size = new Size(130, 32),
            BackColor = Color.FromArgb(241, 245, 249),
            ForeColor = Color.FromArgb(30, 41, 59),
            FlatStyle = FlatStyle.Flat,
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Regular),
            Cursor = Cursors.Hand
        };
        _btnRefreshStatus.FlatAppearance.BorderColor = Color.FromArgb(203, 213, 225);
        _btnRefreshStatus.Click += async (_, _) => await RefreshAuthStatusAsync();

        var lblHelp = new Label
        {
            Text = "1. Klik 'Buka Browser Login' lalu masuk + isi OTP di jendela Chrome.\r\n2. Jika status belum otomatis berubah, klik 'Sudah Selesai Login' untuk memeriksa & menyimpan sesi ke data/auth/state.json.",
            Location = new Point(14, 90),
            Size = new Size(650, 48),
            Font = new Font(Font.FontFamily, 8f, FontStyle.Regular),
            ForeColor = Color.FromArgb(100, 116, 139)
        };

        _grpPortal.Controls.Add(_lblStatus);
        _grpPortal.Controls.Add(_btnOpenLogin);
        _grpPortal.Controls.Add(_btnConfirmLogin);
        _grpPortal.Controls.Add(_btnRefreshStatus);
        _grpPortal.Controls.Add(lblHelp);
        Controls.Add(_grpPortal);

        _pollTimer = new System.Windows.Forms.Timer { Interval = 1500 };
        _pollTimer.Tick += async (_, _) => await PollDuringLoginAsync();
    }

    private void SetConfirmButtonActive(bool active)
    {
        _btnConfirmLogin.Enabled = active;
        if (active)
        {
            _btnConfirmLogin.BackColor = Color.FromArgb(37, 99, 235);
            _btnConfirmLogin.ForeColor = Color.White;
        }
        else
        {
            _btnConfirmLogin.BackColor = Color.FromArgb(226, 232, 240);
            _btnConfirmLogin.ForeColor = Color.FromArgb(71, 85, 105);
        }
    }

    private async Task PollDuringLoginAsync()
    {
        if (!_isLoginRunning || _isPollingTick || IsDisposed)
        {
            return;
        }

        _isPollingTick = true;
        try
        {
            await RefreshAuthStatusAsync(onlyUpdateIfRelevant: true);
        }
        finally
        {
            _isPollingTick = false;
        }
    }

    /// <summary>
    /// Refreshes session status from backend GET /api/portal/auth-status.
    /// </summary>
    public async Task RefreshAuthStatusAsync(bool onlyUpdateIfRelevant = false)
    {
        if (IsDisposed) return;

        try
        {
            var res = await _apiClient.GetPortalAuthStatusAsync();
            if (IsDisposed) return;

            if (res != null && res.Authenticated)
            {
                IsAuthenticated = true;
                _lblStatus.Text = $"🟢 Sesi Aktif ({res.Username ?? "User Terautentikasi"})";
                _lblStatus.ForeColor = Color.FromArgb(22, 101, 52);
                SetConfirmButtonActive(false);
                _btnOpenLogin.Enabled = true;
                _pollTimer.Stop();
            }
            else if (res != null && res.LoginInProgress)
            {
                IsAuthenticated = false;
                _lblStatus.Text = $"⏳ {res.LoginMessage ?? "Browser Chrome terbuka. Login lalu klik 'Sudah Selesai Login'."}";
                _lblStatus.ForeColor = Color.FromArgb(30, 64, 175);
                SetConfirmButtonActive(true);
                _btnOpenLogin.Enabled = false;
            }
            else if (!onlyUpdateIfRelevant)
            {
                IsAuthenticated = false;
                _lblStatus.Text = "⚪ Sesi Belum Ada / Kedaluwarsa (Silakan Login)";
                _lblStatus.ForeColor = Color.FromArgb(100, 116, 139);
                SetConfirmButtonActive(_isLoginRunning);
                _btnOpenLogin.Enabled = !_isLoginRunning;
            }
        }
        catch (Exception ex)
        {
            if (IsDisposed) return;
            if (!onlyUpdateIfRelevant)
            {
                _lblStatus.Text = $"⚠️ Gagal membaca status: {ex.Message}";
                _lblStatus.ForeColor = Color.FromArgb(185, 28, 28);
            }
        }
    }

    /// <summary>
    /// Launches interactive Playwright browser login and polls status until finished or manually confirmed.
    /// </summary>
    public async Task OpenPortalLoginAsync()
    {
        if (IsDisposed) return;

        _isLoginRunning = true;
        _btnOpenLogin.Enabled = false;
        SetConfirmButtonActive(true);
        _lblStatus.Text = "⏳ Meluncurkan browser Chrome untuk login Portal MagangHub...";
        _lblStatus.ForeColor = Color.FromArgb(71, 85, 105);
        _pollTimer.Start();

        try
        {
            var res = await _apiClient.OpenPortalLoginAsync(300);
            if (IsDisposed) return;

            if (res != null && res.Success)
            {
                _isLoginRunning = false;
                _pollTimer.Stop();
                SetConfirmButtonActive(false);
                _lblStatus.Text = res.Authenticated ? "🟢 Login Berhasil!" : "ℹ️ Sesi login selesai.";
                _lblStatus.ForeColor = Color.FromArgb(22, 101, 52);
                await RefreshAuthStatusAsync();
            }
            else if (res != null && res.AlreadyInProgress)
            {
                _lblStatus.Text = $"⏳ {res.Message}";
                _lblStatus.ForeColor = Color.FromArgb(30, 64, 175);
                SetConfirmButtonActive(true);
                return; // Keep polling timer & confirm button active for existing session
            }
            else
            {
                _isLoginRunning = false;
                _pollTimer.Stop();
                SetConfirmButtonActive(false);
                _lblStatus.Text = $"🔴 {res?.Message ?? "Gagal membuka login."}";
                _lblStatus.ForeColor = Color.FromArgb(185, 28, 28);
            }
        }
        catch (Exception ex)
        {
            if (IsDisposed) return;
            _isLoginRunning = false;
            _pollTimer.Stop();
            SetConfirmButtonActive(false);
            _lblStatus.Text = $"🔴 Error: {ex.Message}";
            _lblStatus.ForeColor = Color.FromArgb(185, 28, 28);
        }
        finally
        {
            if (!IsDisposed && !_isLoginRunning)
            {
                _btnOpenLogin.Enabled = true;
            }
        }
    }

    /// <summary>
    /// Asks the backend to immediately check the open Chrome tab, navigate if needed, and save the session.
    /// </summary>
    public async Task ConfirmPortalLoginAsync()
    {
        if (IsDisposed) return;

        _btnConfirmLogin.Enabled = false;
        _lblStatus.Text = "⏳ Memeriksa halaman portal & menyimpan sesi...";
        _lblStatus.ForeColor = Color.FromArgb(30, 64, 175);

        try
        {
            var res = await _apiClient.ConfirmPortalLoginAsync();
            if (IsDisposed) return;

            if (res != null && res.Authenticated)
            {
                _isLoginRunning = false;
                _pollTimer.Stop();
                _lblStatus.Text = "🟢 Login Berhasil! Sesi tersimpan.";
                _lblStatus.ForeColor = Color.FromArgb(22, 101, 52);
                await RefreshAuthStatusAsync();
            }
            else
            {
                _lblStatus.Text = $"⚠️ {res?.Message ?? "Sesi belum terdeteksi. Pastikan sudah login di Chrome lalu klik lagi."}";
                _lblStatus.ForeColor = Color.FromArgb(180, 83, 9);
                SetConfirmButtonActive(true);
            }
        }
        catch (Exception ex)
        {
            if (IsDisposed) return;
            _lblStatus.Text = $"🔴 Error konfirmasi login: {ex.Message}";
            _lblStatus.ForeColor = Color.FromArgb(185, 28, 28);
            SetConfirmButtonActive(true);
        }
    }

    protected override void Dispose(bool disposing)
    {
        if (disposing)
        {
            _pollTimer.Stop();
            _pollTimer.Dispose();
            if (_isLoginRunning)
            {
                _isLoginRunning = false;
                _ = _apiClient.CancelPortalLoginAsync();
            }
        }
        base.Dispose(disposing);
    }
}
