using System.Drawing;
using System.Windows.Forms;
using MagangLog.Desktop.Models;
using MagangLog.Desktop.Services;

namespace MagangLog.Desktop.Controls;

/// <summary>
/// Panel for Step 3 of the onboarding wizard allowing interns to describe their role,
/// predict application detection keywords with AI, select offline presets, and review keywords.
/// </summary>
public class JobRolePanel : Panel
{
    private readonly BackendApiClient _apiClient;
    private readonly List<WorkProfile> _presets = new();

    private readonly TextBox _txtDescription;
    private readonly Button _btnPredict;
    private readonly ComboBox _cboPresets;
    private readonly Panel _pnlBanner;
    private readonly Label _lblBanner;
    private readonly KeywordListPanel _keywordPanel;
    private bool _isErrorBanner = false;

    public KeywordListPanel KeywordPanel => _keywordPanel;

    public string Description
    {
        get => _txtDescription.Text.Trim();
        set => _txtDescription.Text = value ?? string.Empty;
    }

    public bool HasValidProfile =>
        !string.IsNullOrWhiteSpace(_keywordPanel.ProfileName) && _keywordPanel.Keywords.Count > 0;

    public bool IsWarningBannerVisible => _pnlBanner.Visible && _isErrorBanner;
    public bool IsBannerVisible => _pnlBanner.Visible;
    public string WarningBannerText => _lblBanner.Text;
    public int PresetCount => _presets.Count;
    public Func<string>? ApiKeyProvider { get; set; }

    public event EventHandler? GateStateChanged;

    public JobRolePanel(BackendApiClient? apiClient = null)
    {
        _apiClient = apiClient ?? new BackendApiClient();

        Dock = DockStyle.Fill;
        BackColor = Color.White;
        Padding = new Padding(8);

        // --- Top Prompt Section ---
        var promptPanel = new Panel
        {
            Dock = DockStyle.Top,
            Height = 110,
            Padding = new Padding(0, 0, 0, 6)
        };

        var lblPrompt = new Label
        {
            Text = "Kamu bekerja sebagai apa? Ceritakan singkat kegiatan harianmu:",
            Dock = DockStyle.Top,
            Height = 22,
            Font = new Font(Font.FontFamily, 9.5f, FontStyle.Bold),
            ForeColor = Color.FromArgb(30, 41, 59)
        };

        _txtDescription = new TextBox
        {
            Dock = DockStyle.Top,
            Multiline = true,
            Height = 52,
            ScrollBars = ScrollBars.Vertical,
            Font = new Font(Font.FontFamily, 9f, FontStyle.Regular),
            PlaceholderText = "Contoh: Saya mengerjakan frontend web dengan React & VS Code, membuat desain di Figma, dan push commit ke Git..."
        };
        _txtDescription.TextChanged += (_, _) => GateStateChanged?.Invoke(this, EventArgs.Empty);

        // Action Row below description
        var actionRow = new Panel
        {
            Dock = DockStyle.Top,
            Height = 34,
            Padding = new Padding(0, 4, 0, 0)
        };

        _btnPredict = new Button
        {
            Text = "✨ Prediksi Kata Kunci",
            Dock = DockStyle.Left,
            Width = 175,
            Height = 30,
            BackColor = Color.FromArgb(37, 99, 235),
            ForeColor = Color.White,
            FlatStyle = FlatStyle.Flat,
            Font = new Font(Font.FontFamily, 9f, FontStyle.Bold),
            Cursor = Cursors.Hand
        };
        _btnPredict.FlatAppearance.BorderSize = 0;
        _btnPredict.Click += async (_, _) => await PredictKeywordsAsync();

        var lblOr = new Label
        {
            Text = "atau",
            Dock = DockStyle.Left,
            Width = 40,
            TextAlign = ContentAlignment.MiddleCenter,
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Regular),
            ForeColor = Color.FromArgb(100, 116, 139)
        };

        _cboPresets = new ComboBox
        {
            Dock = DockStyle.Left,
            Width = 200,
            DropDownStyle = ComboBoxStyle.DropDownList,
            Font = new Font(Font.FontFamily, 9f, FontStyle.Regular)
        };
        _cboPresets.Items.Add("Pilih Preset Standar...");
        _cboPresets.SelectedIndex = 0;
        _cboPresets.SelectedIndexChanged += (_, _) => HandlePresetSelectionChanged();

        actionRow.Controls.Add(_cboPresets);
        actionRow.Controls.Add(lblOr);
        actionRow.Controls.Add(_btnPredict);

        promptPanel.Controls.Add(actionRow);
        promptPanel.Controls.Add(_txtDescription);
        promptPanel.Controls.Add(lblPrompt);

        // --- Status / Warning Banner ---
        _pnlBanner = new Panel
        {
            Dock = DockStyle.Top,
            Height = 36,
            Visible = false,
            BackColor = Color.FromArgb(254, 242, 242), // light red/amber
            Padding = new Padding(10, 8, 10, 8)
        };

        _lblBanner = new Label
        {
            Dock = DockStyle.Fill,
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Regular),
            ForeColor = Color.FromArgb(153, 27, 27),
            TextAlign = ContentAlignment.MiddleLeft
        };
        _pnlBanner.Controls.Add(_lblBanner);

        // --- Information Label ---
        var infoPanel = new Panel
        {
            Dock = DockStyle.Top,
            Height = 28,
            Padding = new Padding(0, 4, 0, 4)
        };

        var lblInfo = new Label
        {
            Text = "ℹ️ Kata kunci ini dicocokkan dengan proses Windows aktif dan judul jendela aplikasi untuk menangkap bukti kegiatan.",
            Dock = DockStyle.Fill,
            Font = new Font(Font.FontFamily, 8f, FontStyle.Italic),
            ForeColor = Color.FromArgb(100, 116, 139)
        };
        infoPanel.Controls.Add(lblInfo);

        // --- Center: Keyword Management Panel ---
        _keywordPanel = new KeywordListPanel
        {
            Dock = DockStyle.Fill
        };
        _keywordPanel.KeywordsChanged += (_, _) => GateStateChanged?.Invoke(this, EventArgs.Empty);

        // Assemble controls (Dock order: bottom-first or standard top-down)
        Controls.Add(_keywordPanel);
        Controls.Add(infoPanel);
        Controls.Add(_pnlBanner);
        Controls.Add(promptPanel);
    }

    /// <summary>
    /// Calls the backend AI prediction service or handles errors gracefully by falling back to manual entry.
    /// </summary>
    public async Task PredictKeywordsAsync()
    {
        var desc = Description;
        if (string.IsNullOrWhiteSpace(desc))
        {
            ShowBanner("Silakan tuliskan deskripsi kegiatan harian Anda terlebih dahulu.", isError: true);
            return;
        }

        _btnPredict.Enabled = false;
        var originalText = _btnPredict.Text;
        _btnPredict.Text = "⏳ Memprediksi...";

        try
        {
            var apiKey = ApiKeyProvider?.Invoke() ?? "";
            var result = await _apiClient.PredictProfileAsync(desc, apiKey);
            if (result != null && result.Profile != null)
            {
                var keywords = result.Profile.ExtractKeywords();
                _keywordPanel.SetProfile(result.Profile.ProfileName, keywords);

                if (result.Source == "gemini")
                {
                    ShowBanner("✅ Kata kunci berhasil diprediksi oleh Gemini AI.", isError: false);
                }
                else
                {
                    ShowBanner("ℹ️ Mode offline: kata kunci diisi dari preset terdekat.", isError: false);
                }
            }
            else
            {
                ShowBanner("⚠️ Gagal melakukan prediksi AI (offline/server tidak merespons). Anda dapat memilih preset atau menambah kata kunci manual.", isError: true);
            }
        }
        catch (Exception ex)
        {
            ShowBanner($"⚠️ Gagal menghubungi layanan AI: {ex.Message}. Silakan gunakan preset atau input manual.", isError: true);
        }
        finally
        {
            _btnPredict.Enabled = true;
            _btnPredict.Text = originalText;
            GateStateChanged?.Invoke(this, EventArgs.Empty);
        }
    }

    /// <summary>
    /// Loads standard presets from the backend to populate the dropdown.
    /// </summary>
    public async Task LoadPresetsAsync()
    {
        try
        {
            var presets = await _apiClient.GetPresetsAsync();
            _presets.Clear();
            _cboPresets.Items.Clear();
            _cboPresets.Items.Add("Pilih Preset Standar...");

            if (presets != null && presets.Count > 0)
            {
                _presets.AddRange(presets);
                foreach (var p in presets)
                {
                    _cboPresets.Items.Add(p.ProfileName);
                }
            }
            _cboPresets.SelectedIndex = 0;
        }
        catch
        {
            // Silently ignore if offline
        }
    }

    /// <summary>
    /// Selects a preset by profile name and populates the keyword panel.
    /// </summary>
    public void SelectPresetByName(string profileName)
    {
        var found = _presets.FirstOrDefault(p =>
            string.Equals(p.ProfileName, profileName, StringComparison.OrdinalIgnoreCase));

        if (found != null)
        {
            _keywordPanel.SetProfile(found.ProfileName, found.ExtractKeywords());
            if (string.IsNullOrWhiteSpace(_txtDescription.Text))
            {
                _txtDescription.Text = found.NaturalDescription;
            }
            HideBanner();
            GateStateChanged?.Invoke(this, EventArgs.Empty);
        }
    }

    private void HandlePresetSelectionChanged()
    {
        if (_cboPresets.SelectedIndex > 0 && _cboPresets.SelectedIndex - 1 < _presets.Count)
        {
            var selectedPreset = _presets[_cboPresets.SelectedIndex - 1];
            SelectPresetByName(selectedPreset.ProfileName);
        }
    }

    private void ShowBanner(string message, bool isError)
    {
        _isErrorBanner = isError;
        _lblBanner.Text = message;
        if (isError)
        {
            _pnlBanner.BackColor = Color.FromArgb(254, 242, 242);
            _lblBanner.ForeColor = Color.FromArgb(153, 27, 27);
        }
        else
        {
            _pnlBanner.BackColor = Color.FromArgb(240, 253, 244);
            _lblBanner.ForeColor = Color.FromArgb(22, 101, 52);
        }
        _pnlBanner.Visible = true;
    }

    private void HideBanner()
    {
        _isErrorBanner = false;
        _pnlBanner.Visible = false;
        _lblBanner.Text = string.Empty;
    }
}
