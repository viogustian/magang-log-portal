using System.Drawing;
using MagangLog.Desktop.Models;
using MagangLog.Desktop.Services;

namespace MagangLog.Desktop.Controls;

/// <summary>
/// Daily logbook draft reviewer and inline editor with real-time character limit enforcement,
/// local draft saving, AI draft regeneration, and portal submission coordination.
/// </summary>
public class DraftEditorPanel : Panel
{
    private readonly BackendApiClient _apiClient;

    public ComboBox KehadiranComboBox { get; }
    public TextBox AktivitasTextBox { get; }
    public TextBox PembelajaranTextBox { get; }
    public TextBox KendalaTextBox { get; }

    public Label AktivitasCharCountLabel { get; }
    public Label PembelajaranCharCountLabel { get; }
    public Label KendalaCharCountLabel { get; }

    public Button SaveDraftButton { get; }
    public Button RegenerateDraftButton { get; }
    public Button ApproveAndSubmitButton { get; }

    public ProgressBar SubmissionProgressBar { get; }
    public Label ProgressStepLabel { get; }

    public EntryDetailResponse? CurrentEntry { get; private set; }

    public event Action? OnDraftUpdated;

    public DraftEditorPanel(BackendApiClient? apiClient = null)
    {
        _apiClient = apiClient ?? new BackendApiClient();

        Dock = DockStyle.Fill;
        AutoScroll = true;
        BackColor = Color.FromArgb(248, 250, 252);
        Padding = new Padding(20, 16, 20, 24);

        // Container with fixed vertical flow
        var mainContainer = new FlowLayoutPanel
        {
            Dock = DockStyle.Top,
            FlowDirection = FlowDirection.TopDown,
            AutoSize = true,
            AutoSizeMode = AutoSizeMode.GrowAndShrink,
            WrapContents = false,
            BackColor = Color.Transparent,
            Width = 620
        };

        // Header Title
        var lblHeader = new Label
        {
            Text = "Draf Logbook Harian",
            Font = new Font(Font.FontFamily, 12f, FontStyle.Bold),
            ForeColor = Color.FromArgb(15, 23, 42),
            AutoSize = true,
            Margin = new Padding(0, 0, 0, 12)
        };
        mainContainer.Controls.Add(lblHeader);

        // 1. Kehadiran GroupBox
        var gbKehadiran = new GroupBox
        {
            Text = "Status Kehadiran",
            Width = 600,
            Height = 65,
            Font = new Font(Font.FontFamily, 9.5f, FontStyle.Bold),
            ForeColor = Color.FromArgb(51, 65, 85),
            Margin = new Padding(0, 0, 0, 10),
            Padding = new Padding(12, 8, 12, 8)
        };
        KehadiranComboBox = new ComboBox
        {
            DropDownStyle = ComboBoxStyle.DropDownList,
            Dock = DockStyle.Fill,
            Font = new Font(Font.FontFamily, 9.5f, FontStyle.Regular),
            Cursor = Cursors.Hand
        };
        KehadiranComboBox.Items.AddRange(new object[] { "Hadir", "Izin", "Sakit", "Cuti" });
        KehadiranComboBox.SelectedItem = "Hadir";
        gbKehadiran.Controls.Add(KehadiranComboBox);
        mainContainer.Controls.Add(gbKehadiran);

        // 2. Aktivitas Utama GroupBox
        AktivitasTextBox = CreateMultilineTextBox();
        AktivitasCharCountLabel = CreateCharCountLabel();
        var gbAktivitas = CreateFieldGroupBox(
            "Aktivitas Utama (Minimal 100 karakter)",
            AktivitasTextBox,
            AktivitasCharCountLabel
        );
        mainContainer.Controls.Add(gbAktivitas);

        // 3. Pembelajaran GroupBox
        PembelajaranTextBox = CreateMultilineTextBox();
        PembelajaranCharCountLabel = CreateCharCountLabel();
        var gbPembelajaran = CreateFieldGroupBox(
            "Pembelajaran / Refleksi (Minimal 100 karakter)",
            PembelajaranTextBox,
            PembelajaranCharCountLabel
        );
        mainContainer.Controls.Add(gbPembelajaran);

        // 4. Kendala & Solusi GroupBox
        KendalaTextBox = CreateMultilineTextBox();
        KendalaCharCountLabel = CreateCharCountLabel();
        var gbKendala = CreateFieldGroupBox(
            "Kendala & Solusi (Minimal 100 karakter)",
            KendalaTextBox,
            KendalaCharCountLabel
        );
        mainContainer.Controls.Add(gbKendala);

        // Hook TextChanged events for live character counting and gate validation
        AktivitasTextBox.TextChanged += (_, _) => UpdateValidationState();
        PembelajaranTextBox.TextChanged += (_, _) => UpdateValidationState();
        KendalaTextBox.TextChanged += (_, _) => UpdateValidationState();

        // 5. Actions Bar
        var actionsPanel = new FlowLayoutPanel
        {
            Width = 600,
            Height = 44,
            FlowDirection = FlowDirection.LeftToRight,
            AutoSize = false,
            WrapContents = false,
            BackColor = Color.Transparent,
            Margin = new Padding(0, 6, 0, 8)
        };

        SaveDraftButton = new Button
        {
            Text = "Simpan Draf",
            Height = 36,
            AutoSize = true,
            Padding = new Padding(14, 0, 14, 0),
            BackColor = Color.White,
            ForeColor = Color.FromArgb(30, 41, 59),
            FlatStyle = FlatStyle.Flat,
            Cursor = Cursors.Hand,
            Margin = new Padding(0, 0, 8, 0),
            Font = new Font(Font.FontFamily, 9.5f, FontStyle.Regular)
        };
        SaveDraftButton.FlatAppearance.BorderColor = Color.FromArgb(203, 213, 225);
        SaveDraftButton.Click += async (_, _) => await SaveDraftAsync();

        RegenerateDraftButton = new Button
        {
            Text = "Regenerate Draf (Gemini)",
            Height = 36,
            AutoSize = true,
            Padding = new Padding(14, 0, 14, 0),
            BackColor = Color.White,
            ForeColor = Color.FromArgb(30, 41, 59),
            FlatStyle = FlatStyle.Flat,
            Cursor = Cursors.Hand,
            Margin = new Padding(0, 0, 8, 0),
            Font = new Font(Font.FontFamily, 9.5f, FontStyle.Regular)
        };
        RegenerateDraftButton.FlatAppearance.BorderColor = Color.FromArgb(203, 213, 225);
        RegenerateDraftButton.Click += async (_, _) => await RegenerateDraftAsync();

        ApproveAndSubmitButton = new Button
        {
            Text = "Setujui & Kirim ke Portal 🚀",
            Height = 36,
            AutoSize = true,
            Padding = new Padding(16, 0, 16, 0),
            BackColor = Color.FromArgb(16, 185, 129),
            ForeColor = Color.White,
            FlatStyle = FlatStyle.Flat,
            Cursor = Cursors.Hand,
            Enabled = false,
            Font = new Font(Font.FontFamily, 9.5f, FontStyle.Bold)
        };
        ApproveAndSubmitButton.FlatAppearance.BorderSize = 0;
        ApproveAndSubmitButton.Click += async (_, _) => await ApproveAndSubmitAsync();

        actionsPanel.Controls.Add(SaveDraftButton);
        actionsPanel.Controls.Add(RegenerateDraftButton);
        actionsPanel.Controls.Add(ApproveAndSubmitButton);
        mainContainer.Controls.Add(actionsPanel);

        // 6. Progress Bar and Step Label
        var progressContainer = new Panel
        {
            Width = 600,
            Height = 44,
            BackColor = Color.Transparent,
            Margin = new Padding(0, 4, 0, 16)
        };

        SubmissionProgressBar = new ProgressBar
        {
            Dock = DockStyle.Top,
            Height = 8,
            Style = ProgressBarStyle.Continuous,
            Value = 0,
            Visible = false
        };

        ProgressStepLabel = new Label
        {
            Dock = DockStyle.Bottom,
            Height = 28,
            Text = "Tahapan Pengiriman: Mengisi Formulir → Mengirim → Memverifikasi Halaman",
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Regular),
            ForeColor = Color.FromArgb(100, 116, 139),
            TextAlign = ContentAlignment.MiddleLeft,
            Visible = false
        };

        progressContainer.Controls.Add(ProgressStepLabel);
        progressContainer.Controls.Add(SubmissionProgressBar);
        mainContainer.Controls.Add(progressContainer);

        Controls.Add(mainContainer);

        // Initial validation check
        UpdateValidationState();
    }

    private static TextBox CreateMultilineTextBox()
    {
        return new TextBox
        {
            Multiline = true,
            ScrollBars = ScrollBars.Vertical,
            Dock = DockStyle.Fill,
            Font = new Font("Segoe UI", 9.5f, FontStyle.Regular),
            ForeColor = Color.FromArgb(15, 23, 42),
            BackColor = Color.White
        };
    }

    private static Label CreateCharCountLabel()
    {
        return new Label
        {
            Dock = DockStyle.Bottom,
            Height = 22,
            Text = "(0/5000 karakter)",
            Font = new Font("Segoe UI", 8.5f, FontStyle.Regular),
            ForeColor = Color.Red,
            TextAlign = ContentAlignment.MiddleRight
        };
    }

    private static GroupBox CreateFieldGroupBox(string title, TextBox textBox, Label charCountLabel)
    {
        var gb = new GroupBox
        {
            Text = title,
            Width = 600,
            Height = 150,
            Font = new Font("Segoe UI", 9.5f, FontStyle.Bold),
            ForeColor = Color.FromArgb(51, 65, 85),
            Margin = new Padding(0, 0, 0, 10),
            Padding = new Padding(10, 8, 10, 6)
        };

        var container = new Panel
        {
            Dock = DockStyle.Fill,
            BackColor = Color.Transparent
        };
        container.Controls.Add(textBox);
        container.Controls.Add(charCountLabel);

        gb.Controls.Add(container);
        return gb;
    }

    /// <summary>
    /// Update live character counts, warning colors, and submit button enable status.
    /// </summary>
    public void UpdateValidationState()
    {
        UpdateCounter(AktivitasTextBox.Text, AktivitasCharCountLabel);
        UpdateCounter(PembelajaranTextBox.Text, PembelajaranCharCountLabel);
        UpdateCounter(KendalaTextBox.Text, KendalaCharCountLabel);

        var canApprove = CharacterCounterHelper.CanApprove(
            AktivitasTextBox.Text,
            PembelajaranTextBox.Text,
            KendalaTextBox.Text
        );

        ApproveAndSubmitButton.Enabled = canApprove;
    }

    private static void UpdateCounter(string text, Label label)
    {
        var count = text?.Length ?? 0;
        label.Text = CharacterCounterHelper.GetCharacterCountText(count);
        label.ForeColor = CharacterCounterHelper.GetCharacterCountColor(count);
    }

    /// <summary>
    /// Load entry details into form fields.
    /// </summary>
    public void LoadEntry(EntryDetailResponse? entry)
    {
        CurrentEntry = entry;
        if (entry == null)
        {
            KehadiranComboBox.SelectedItem = "Hadir";
            AktivitasTextBox.Text = string.Empty;
            PembelajaranTextBox.Text = string.Empty;
            KendalaTextBox.Text = string.Empty;
            UpdateValidationState();
            return;
        }

        if (KehadiranComboBox.Items.Contains(entry.Kehadiran))
        {
            KehadiranComboBox.SelectedItem = entry.Kehadiran;
        }

        AktivitasTextBox.Text = entry.Aktivitas ?? string.Empty;
        PembelajaranTextBox.Text = entry.Pembelajaran ?? string.Empty;
        KendalaTextBox.Text = entry.Kendala ?? string.Empty;

        UpdateValidationState();
    }

    /// <summary>
    /// Persist current text fields to backend ledger via POST /api/entry/edit.
    /// </summary>
    public async Task<bool> SaveDraftAsync(string? workDate = null)
    {
        var targetDate = workDate ?? CurrentEntry?.WorkDate;
        var req = new EditEntryRequest
        {
            WorkDate = targetDate,
            Kehadiran = KehadiranComboBox.SelectedItem?.ToString() ?? "Hadir",
            Aktivitas = AktivitasTextBox.Text,
            Pembelajaran = PembelajaranTextBox.Text,
            Kendala = KendalaTextBox.Text
        };

        SaveDraftButton.Enabled = false;
        try
        {
            var res = await _apiClient.EditEntryAsync(req);
            if (res != null && res.Success)
            {
                OnDraftUpdated?.Invoke();
                return true;
            }

            MessageBox.Show(
                "Gagal menyimpan draf logbook. Pastikan seluruh kolom terisi.",
                "Peringatan",
                MessageBoxButtons.OK,
                MessageBoxIcon.Warning);
            return false;
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                $"Terjadi kesalahan saat menyimpan draf: {ex.Message}",
                "Kesalahan",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
            return false;
        }
        finally
        {
            SaveDraftButton.Enabled = true;
        }
    }

    /// <summary>
    /// Request fresh Gemini AI draft via POST /api/entry/draft.
    /// </summary>
    public async Task<bool> RegenerateDraftAsync(string? workDate = null)
    {
        var targetDate = workDate ?? CurrentEntry?.WorkDate;
        RegenerateDraftButton.Enabled = false;
        try
        {
            var res = await _apiClient.DraftEntryAsync(targetDate);
            if (res != null && res.Success && res.Draft != null)
            {
                LoadEntry(res.Draft);
                OnDraftUpdated?.Invoke();
                return true;
            }

            MessageBox.Show(
                "Gagal menyusun ulang draf dengan Gemini. Pastikan koneksi backend aktif.",
                "Peringatan",
                MessageBoxButtons.OK,
                MessageBoxIcon.Warning);
            return false;
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                $"Terjadi kesalahan saat menyusun ulang draf: {ex.Message}",
                "Kesalahan",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
            return false;
        }
        finally
        {
            RegenerateDraftButton.Enabled = true;
        }
    }

    /// <summary>
    /// Coordinate approval and automated submission to Kemnaker Monev portal.
    /// </summary>
    public async Task<bool> ApproveAndSubmitAsync(string? workDate = null)
    {
        if (!CharacterCounterHelper.CanApprove(AktivitasTextBox.Text, PembelajaranTextBox.Text, KendalaTextBox.Text))
        {
            MessageBox.Show(
                "Kolom Aktivitas, Pembelajaran, dan Kendala harus memiliki panjang minimal 100 karakter sebelum disetujui.",
                "Validasi Belum Terpenuhi",
                MessageBoxButtons.OK,
                MessageBoxIcon.Warning);
            return false;
        }

        var targetDate = workDate ?? CurrentEntry?.WorkDate;
        SetSubmissionProgress(33, "Tahap 1/3: Mengisi Formulir...");

        try
        {
            // First save edits to ensure ledger is in sync
            var saveReq = new EditEntryRequest
            {
                WorkDate = targetDate,
                Kehadiran = KehadiranComboBox.SelectedItem?.ToString() ?? "Hadir",
                Aktivitas = AktivitasTextBox.Text,
                Pembelajaran = PembelajaranTextBox.Text,
                Kendala = KendalaTextBox.Text
            };
            await _apiClient.EditEntryAsync(saveReq);

            SetSubmissionProgress(66, "Tahap 2/3: Mengirim Logbook ke Portal...");

            var res = await _apiClient.ApproveEntryAsync(targetDate);
            if (res != null && res.Success)
            {
                SetSubmissionProgress(100, "Tahap 3/3: Memverifikasi Halaman Portal Selesai ✅");
                OnDraftUpdated?.Invoke();
                return true;
            }

            var errMsg = res?.ErrorMessage ?? "Backend mengembalikan status gagal.";
            MessageBox.Show(
                $"Gagal mengirim logbook ke portal Monev Kemnaker:\n{errMsg}",
                "Pengiriman Gagal",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
            return false;
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                $"Terjadi kesalahan koneksi saat pengiriman: {ex.Message}",
                "Kesalahan Jaringan",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
            return false;
        }
        finally
        {
            ResetSubmissionProgress();
        }
    }

    private void SetSubmissionProgress(int progressValue, string stepText)
    {
        SubmissionProgressBar.Visible = true;
        SubmissionProgressBar.Value = Math.Clamp(progressValue, 0, 100);
        ProgressStepLabel.Visible = true;
        ProgressStepLabel.Text = stepText;
        ApproveAndSubmitButton.Enabled = false;
        SaveDraftButton.Enabled = false;
        RegenerateDraftButton.Enabled = false;
    }

    private void ResetSubmissionProgress()
    {
        SubmissionProgressBar.Visible = false;
        ProgressStepLabel.Visible = false;
        SaveDraftButton.Enabled = true;
        RegenerateDraftButton.Enabled = true;
        UpdateValidationState();
    }
}
