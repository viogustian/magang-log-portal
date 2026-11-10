using System.Diagnostics;
using MagangLog.Desktop.Models;
using MagangLog.Desktop.Services;

namespace MagangLog.Desktop.Controls;

/// <summary>
/// First-class onboarding card for configuring, testing, and selecting Google AI Studio (Gemini)
/// credentials in Step 1 of the Setup Wizard.
/// </summary>
public class GeminiCredentialsCard : Panel
{
    public const string GoogleAiStudioUrl = "https://aistudio.google.com/app/apikey";

    private readonly BackendApiClient _apiClient;
    private readonly TextBox _txtApiKey;
    private readonly CheckBox _chkShow;
    private readonly ComboBox _cboModel;
    private readonly Button _btnRefreshModels;
    private readonly Button _btnTest;
    private readonly Label _lblStatus;
    private readonly LinkLabel _lnkGetApiKey;

    public TextBox ApiKeyTextBox => _txtApiKey;
    public CheckBox ShowApiKeyCheckBox => _chkShow;
    public ComboBox ModelComboBox => _cboModel;
    public Button RefreshModelsButton => _btnRefreshModels;
    public Button TestButton => _btnTest;
    public Label StatusLabel => _lblStatus;
    public LinkLabel GetApiKeyLink => _lnkGetApiKey;

    public string ApiKey
    {
        get => _txtApiKey.Text.Trim();
        set
        {
            var clean = (value ?? string.Empty).Trim();
            if (_txtApiKey.Text != clean)
            {
                _txtApiKey.Text = clean;
            }
            UpdateStatusVisuals();
            GateStateChanged?.Invoke(this, EventArgs.Empty);
        }
    }

    public string SelectedModel
    {
        get => _cboModel.SelectedItem?.ToString() ?? "gemini-3.5-flash";
        set
        {
            if (string.IsNullOrWhiteSpace(value)) return;
            var clean = value.StartsWith("models/") ? value.Substring(7) : value;
            if (!_cboModel.Items.Contains(clean))
            {
                _cboModel.Items.Add(clean);
            }
            _cboModel.SelectedItem = clean;
        }
    }

    public bool IsKeyProvided => !string.IsNullOrWhiteSpace(ApiKey);
    public bool IsTestedSuccessfully { get; private set; } = false;

    public Action<string>? UrlOpener { get; set; } = url =>
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
                $"Gagal membuka browser: {ex.Message}",
                "Browser Error",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
        }
    };

    public event EventHandler? GateStateChanged;

    public GeminiCredentialsCard(BackendApiClient? apiClient = null)
    {
        _apiClient = apiClient ?? new BackendApiClient();

        Dock = DockStyle.Top;
        AutoSize = true;
        MinimumSize = new Size(0, 190);
        BackColor = Color.White;
        Padding = new Padding(0, 0, 0, 10);

        var grp = new GroupBox
        {
            Text = "1. Kredensial Google AI Studio (Gemini) — Wajib untuk Penyusunan Draf Otomatis",
            Dock = DockStyle.Top,
            Height = 185,
            Font = new Font(Font.FontFamily, 9f, FontStyle.Bold),
            ForeColor = Color.FromArgb(30, 41, 59),
            BackColor = Color.FromArgb(248, 250, 252),
            Padding = new Padding(12, 10, 12, 10)
        };

        var lblKey = new Label
        {
            Text = "Google AI Studio API Key:",
            Location = new Point(14, 24),
            Size = new Size(180, 18),
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Regular),
            ForeColor = Color.FromArgb(51, 65, 85)
        };

        _lnkGetApiKey = new LinkLabel
        {
            Text = "Belum punya kunci? Dapatkan gratis di Google AI Studio 🌐",
            Location = new Point(200, 24),
            Size = new Size(380, 18),
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Regular),
            LinkColor = Color.FromArgb(37, 99, 235),
            Cursor = Cursors.Hand
        };
        _lnkGetApiKey.LinkClicked += (_, _) => OpenApiKeyPortal();

        _txtApiKey = new TextBox
        {
            Location = new Point(16, 44),
            Size = new Size(530, 24),
            UseSystemPasswordChar = true,
            Font = new Font("Consolas", 9.5f, FontStyle.Regular),
            PlaceholderText = "Tempel API key Google AI Studio (AIzaSy...)"
        };
        _txtApiKey.TextChanged += (_, _) =>
        {
            IsTestedSuccessfully = false;
            UpdateStatusVisuals();
            GateStateChanged?.Invoke(this, EventArgs.Empty);
        };

        _chkShow = new CheckBox
        {
            Text = "Tampilkan",
            Location = new Point(555, 45),
            Size = new Size(95, 22),
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Regular)
        };
        _chkShow.CheckedChanged += (_, _) => _txtApiKey.UseSystemPasswordChar = !_chkShow.Checked;

        var lblModel = new Label
        {
            Text = "Model Gemini Terpilih (Free Tier):",
            Location = new Point(14, 76),
            Size = new Size(200, 18),
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Regular),
            ForeColor = Color.FromArgb(51, 65, 85)
        };

        _cboModel = new ComboBox
        {
            Location = new Point(16, 96),
            Size = new Size(240, 24),
            DropDownStyle = ComboBoxStyle.DropDownList,
            Font = new Font("Segoe UI", 9f, FontStyle.Regular)
        };
        _cboModel.Items.AddRange(new object[]
        {
            "gemini-3.5-flash",
            "gemini-3.8-flash",
            "gemini-flash-latest",
            "gemini-3.1-flash-lite",
            "gemini-3.7-flash"
        });
        _cboModel.SelectedItem = "gemini-3.5-flash";

        _btnRefreshModels = new Button
        {
            Text = "🔄 Perbarui Model",
            Location = new Point(265, 95),
            Size = new Size(130, 26),
            BackColor = Color.FromArgb(241, 245, 249),
            ForeColor = Color.FromArgb(30, 41, 59),
            FlatStyle = FlatStyle.Flat,
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Regular),
            Cursor = Cursors.Hand
        };
        _btnRefreshModels.FlatAppearance.BorderColor = Color.FromArgb(203, 213, 225);
        _btnRefreshModels.Click += async (_, _) => await RefreshModelsAsync();

        _btnTest = new Button
        {
            Text = "⚡ Tes Koneksi",
            Location = new Point(16, 132),
            Size = new Size(120, 30),
            BackColor = Color.FromArgb(37, 99, 235),
            ForeColor = Color.White,
            FlatStyle = FlatStyle.Flat,
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Bold),
            Cursor = Cursors.Hand
        };
        _btnTest.FlatAppearance.BorderSize = 0;
        _btnTest.Click += async (_, _) => await TestConnectionAsync();

        _lblStatus = new Label
        {
            Text = "Status: Belum diisi",
            Location = new Point(145, 138),
            Size = new Size(500, 20),
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Regular),
            ForeColor = Color.FromArgb(100, 116, 139)
        };

        grp.Controls.Add(lblKey);
        grp.Controls.Add(_lnkGetApiKey);
        grp.Controls.Add(_txtApiKey);
        grp.Controls.Add(_chkShow);
        grp.Controls.Add(lblModel);
        grp.Controls.Add(_cboModel);
        grp.Controls.Add(_btnRefreshModels);
        grp.Controls.Add(_btnTest);
        grp.Controls.Add(_lblStatus);

        Controls.Add(grp);

        // Pre-check environment variable if present
        var envKey = Environment.GetEnvironmentVariable("GEMINI_API_KEY");
        if (!string.IsNullOrWhiteSpace(envKey))
        {
            _txtApiKey.Text = envKey.Trim();
            _lblStatus.Text = "🟢 Kunci API terdeteksi dari lingkungan sistem.";
            _lblStatus.ForeColor = Color.FromArgb(22, 101, 52);
        }
    }

    public void OpenApiKeyPortal()
    {
        UrlOpener?.Invoke(GoogleAiStudioUrl);
    }

    public async Task<bool> TestConnectionAsync()
    {
        var key = ApiKey;
        if (string.IsNullOrWhiteSpace(key))
        {
            _lblStatus.Text = "⚠️ Masukkan API key terlebih dahulu sebelum mengetes.";
            _lblStatus.ForeColor = Color.FromArgb(185, 28, 28);
            IsTestedSuccessfully = false;
            GateStateChanged?.Invoke(this, EventArgs.Empty);
            return false;
        }

        _btnTest.Enabled = false;
        _btnTest.Text = "⏳ Menguji...";
        _lblStatus.Text = "Menghubungi Google AI Studio...";
        _lblStatus.ForeColor = Color.FromArgb(71, 85, 105);

        try
        {
            var res = await _apiClient.TestGeminiAsync(key);
            if (res != null && res.Valid)
            {
                _lblStatus.Text = $"🟢 Kunci API valid & terhubung (Model: {res.Model ?? SelectedModel}).";
                _lblStatus.ForeColor = Color.FromArgb(22, 101, 52);
                IsTestedSuccessfully = true;
                _ = RefreshModelsAsync();
                GateStateChanged?.Invoke(this, EventArgs.Empty);
                return true;
            }

            _lblStatus.Text = "🔴 Kunci API tidak valid atau kuota habis.";
            _lblStatus.ForeColor = Color.FromArgb(185, 28, 28);
            IsTestedSuccessfully = false;
            GateStateChanged?.Invoke(this, EventArgs.Empty);
            return false;
        }
        catch (Exception ex)
        {
            _lblStatus.Text = $"🔴 Gagal terhubung ke Google AI Studio: {ex.Message}";
            _lblStatus.ForeColor = Color.FromArgb(185, 28, 28);
            IsTestedSuccessfully = false;
            GateStateChanged?.Invoke(this, EventArgs.Empty);
            return false;
        }
        finally
        {
            _btnTest.Enabled = true;
            _btnTest.Text = "⚡ Tes Koneksi";
        }
    }

    public async Task RefreshModelsAsync()
    {
        var key = ApiKey;
        if (string.IsNullOrWhiteSpace(key)) return;

        try
        {
            var modelsRes = await _apiClient.GetGeminiModelsAsync(key);
            if (modelsRes != null && modelsRes.Models.Count > 0)
            {
                var currentSelection = SelectedModel;
                _cboModel.Items.Clear();

                foreach (var m in modelsRes.Models)
                {
                    var cleanName = m.Id.StartsWith("models/") ? m.Id.Substring(7) : m.Id;
                    if (!_cboModel.Items.Contains(cleanName))
                    {
                        _cboModel.Items.Add(cleanName);
                    }
                }

                if (_cboModel.Items.Contains(currentSelection))
                {
                    _cboModel.SelectedItem = currentSelection;
                }
                else if (!string.IsNullOrWhiteSpace(modelsRes.ActiveModel))
                {
                    SelectedModel = modelsRes.ActiveModel;
                }
                else
                {
                    _cboModel.SelectedIndex = 0;
                }
            }
        }
        catch
        {
            // Suppress refresh errors gracefully
        }
    }

    public async Task LoadSavedKeyAsync()
    {
        if (!string.IsNullOrWhiteSpace(ApiKey)) return;

        var envKey = Environment.GetEnvironmentVariable("GEMINI_API_KEY");
        if (!string.IsNullOrWhiteSpace(envKey))
        {
            ApiKey = envKey.Trim();
            _lblStatus.Text = "🟢 Kunci API terdeteksi dari lingkungan sistem.";
            _lblStatus.ForeColor = Color.FromArgb(22, 101, 52);
            return;
        }

        try
        {
            var cfg = await _apiClient.GetAppConfigAsync();
            if (cfg != null && cfg.Llm != null && !string.IsNullOrWhiteSpace(cfg.Llm.ApiKey))
            {
                ApiKey = cfg.Llm.ApiKey;
                if (!string.IsNullOrWhiteSpace(cfg.Llm.Model))
                {
                    SelectedModel = cfg.Llm.Model;
                }
                _lblStatus.Text = "🟢 Kunci API tersimpan di konfigurasi sistem.";
                _lblStatus.ForeColor = Color.FromArgb(22, 101, 52);
            }
        }
        catch
        {
            // Backend offline or config unavailable
        }
    }

    private void UpdateStatusVisuals()
    {
        if (string.IsNullOrWhiteSpace(_txtApiKey.Text))
        {
            _lblStatus.Text = "Status: Belum diisi";
            _lblStatus.ForeColor = Color.FromArgb(100, 116, 139);
        }
        else if (!IsTestedSuccessfully)
        {
            _lblStatus.Text = "Status: Kunci telah diinput (klik 'Tes Koneksi' untuk memverifikasi)";
            _lblStatus.ForeColor = Color.FromArgb(71, 85, 105);
        }
    }
}
