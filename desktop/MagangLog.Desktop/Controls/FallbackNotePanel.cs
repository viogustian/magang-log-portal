using System.Drawing;
using MagangLog.Desktop.Models;
using MagangLog.Desktop.Services;

namespace MagangLog.Desktop.Controls;

/// <summary>
/// Quick reflection note fallback panel (ADR-0003) displayed when today's evidence is empty
/// or pipeline requires manual input (PERLU_INPUT/GATED).
/// </summary>
public class FallbackNotePanel : Panel
{
    private readonly BackendApiClient _apiClient;
    private string _targetDate = DateTime.Today.ToString("yyyy-MM-dd");

    public ComboBox CategoryComboBox { get; }
    public TextBox NoteTextBox { get; }
    public Label CharCountLabel { get; }
    public Label ErrorLabel { get; }
    public Label StatusLabel { get; }

    public Button SendNoteButton { get; }
    public Button SwitchToEditorButton { get; }

    public event Action? OnNoteSubmitted;
    public event Action? OnSwitchToEditorRequested;

    public FallbackNotePanel(BackendApiClient? apiClient = null)
    {
        _apiClient = apiClient ?? new BackendApiClient();

        Dock = DockStyle.Fill;
        AutoScroll = true;
        BackColor = Color.FromArgb(248, 250, 252);
        Padding = new Padding(24, 20, 24, 24);

        var mainLayout = new FlowLayoutPanel
        {
            Dock = DockStyle.Top,
            FlowDirection = FlowDirection.TopDown,
            AutoSize = true,
            AutoSizeMode = AutoSizeMode.GrowAndShrink,
            WrapContents = false,
            BackColor = Color.Transparent,
            Width = 620
        };

        // Notice / Alert Card
        var noticeCard = new Panel
        {
            Width = 600,
            Height = 90,
            BackColor = Color.FromArgb(254, 243, 199), // Amber-100
            Margin = new Padding(0, 0, 0, 16),
            Padding = new Padding(16, 12, 16, 12)
        };

        var noticeTitle = new Label
        {
            Text = "⚠️  Catatan Refleksi Cepat — Butuh Input Kegiatan",
            Font = new Font("Segoe UI", 11f, FontStyle.Bold),
            ForeColor = Color.FromArgb(146, 64, 14), // Amber-800
            Dock = DockStyle.Top,
            Height = 24
        };

        var noticeDesc = new Label
        {
            Text = "Bukti aktivitas otomatis hari ini belum tersedia atau sistem memerlukan input manual (ADR-0003). " +
                   "Tuliskan ringkasan kegiatan, pembelajaran, atau kendala Anda di bawah untuk melanjutkan pipeline logbook.",
            Font = new Font("Segoe UI", 9f, FontStyle.Regular),
            ForeColor = Color.FromArgb(180, 83, 9), // Amber-700
            Dock = DockStyle.Fill
        };

        noticeCard.Controls.Add(noticeDesc);
        noticeCard.Controls.Add(noticeTitle);
        mainLayout.Controls.Add(noticeCard);

        // Category Group
        var categoryGroup = new GroupBox
        {
            Text = "Kategori Catatan",
            Width = 600,
            Height = 68,
            Font = new Font("Segoe UI", 9.5f, FontStyle.Bold),
            ForeColor = Color.FromArgb(51, 65, 85),
            Margin = new Padding(0, 0, 0, 12),
            Padding = new Padding(12, 8, 12, 8)
        };

        CategoryComboBox = new ComboBox
        {
            DropDownStyle = ComboBoxStyle.DropDownList,
            Dock = DockStyle.Fill,
            Font = new Font("Segoe UI", 9.5f, FontStyle.Regular),
            Cursor = Cursors.Hand
        };
        CategoryComboBox.Items.AddRange(new object[] { "Aktivitas", "Pembelajaran", "Kendala" });
        CategoryComboBox.SelectedItem = "Aktivitas";
        categoryGroup.Controls.Add(CategoryComboBox);
        mainLayout.Controls.Add(categoryGroup);

        // Note Input Group
        var noteGroup = new GroupBox
        {
            Text = "Isi Catatan Refleksi Ringkas",
            Width = 600,
            Height = 200,
            Font = new Font("Segoe UI", 9.5f, FontStyle.Bold),
            ForeColor = Color.FromArgb(51, 65, 85),
            Margin = new Padding(0, 0, 0, 10),
            Padding = new Padding(12, 8, 12, 8)
        };

        NoteTextBox = new TextBox
        {
            Multiline = true,
            Dock = DockStyle.Fill,
            ScrollBars = ScrollBars.Vertical,
            Font = new Font("Segoe UI", 10f, FontStyle.Regular),
            ForeColor = Color.FromArgb(15, 23, 42),
            BackColor = Color.White
        };
        NoteTextBox.TextChanged += (s, e) => UpdateCharCount();

        var noteBottomBar = new Panel
        {
            Dock = DockStyle.Bottom,
            Height = 24,
            BackColor = Color.Transparent
        };

        CharCountLabel = new Label
        {
            Text = "0 / 5000 karakter",
            Font = new Font("Segoe UI", 8.5f, FontStyle.Regular),
            ForeColor = Color.FromArgb(100, 116, 139),
            Dock = DockStyle.Right,
            AutoSize = true
        };

        noteBottomBar.Controls.Add(CharCountLabel);
        noteGroup.Controls.Add(NoteTextBox);
        noteGroup.Controls.Add(noteBottomBar);
        mainLayout.Controls.Add(noteGroup);

        // Error & Status Feedback Labels
        ErrorLabel = new Label
        {
            Text = "Catatan tidak boleh kosong.",
            Font = new Font("Segoe UI", 9f, FontStyle.Bold),
            ForeColor = Color.FromArgb(220, 38, 38), // Red-600
            Width = 600,
            Height = 22,
            Visible = false,
            Margin = new Padding(0, 0, 0, 6)
        };
        mainLayout.Controls.Add(ErrorLabel);

        StatusLabel = new Label
        {
            Text = "Catatan berhasil dikirim!",
            Font = new Font("Segoe UI", 9f, FontStyle.Bold),
            ForeColor = Color.FromArgb(22, 163, 74), // Green-600
            Width = 600,
            Height = 22,
            Visible = false,
            Margin = new Padding(0, 0, 0, 6)
        };
        mainLayout.Controls.Add(StatusLabel);

        // Action Buttons Bar
        var buttonsBar = new FlowLayoutPanel
        {
            FlowDirection = FlowDirection.LeftToRight,
            Width = 600,
            Height = 44,
            BackColor = Color.Transparent,
            Margin = new Padding(0, 8, 0, 0)
        };

        SendNoteButton = new Button
        {
            Text = "Kirim Catatan 🚀",
            Width = 160,
            Height = 38,
            BackColor = Color.FromArgb(2, 132, 199), // Sky-600
            ForeColor = Color.White,
            FlatStyle = FlatStyle.Flat,
            Font = new Font("Segoe UI", 9.5f, FontStyle.Bold),
            Cursor = Cursors.Hand,
            Margin = new Padding(0, 0, 12, 0)
        };
        SendNoteButton.FlatAppearance.BorderSize = 0;
        SendNoteButton.Click += async (s, e) => await SubmitNoteAsync();

        SwitchToEditorButton = new Button
        {
            Text = "Buka Editor Draf Tetap 📝",
            Width = 200,
            Height = 38,
            BackColor = Color.FromArgb(226, 232, 240), // Slate-200
            ForeColor = Color.FromArgb(30, 41, 59), // Slate-800
            FlatStyle = FlatStyle.Flat,
            Font = new Font("Segoe UI", 9f, FontStyle.Regular),
            Cursor = Cursors.Hand
        };
        SwitchToEditorButton.FlatAppearance.BorderSize = 0;
        SwitchToEditorButton.Click += (s, e) => SwitchToEditor();

        buttonsBar.Controls.Add(SendNoteButton);
        buttonsBar.Controls.Add(SwitchToEditorButton);
        mainLayout.Controls.Add(buttonsBar);

        Controls.Add(mainLayout);
        UpdateCharCount();
    }

    public void SetTargetDate(string? dateStr)
    {
        if (!string.IsNullOrWhiteSpace(dateStr))
        {
            _targetDate = dateStr.Trim();
        }
    }

    public string GetSelectedCategoryKey()
    {
        var selected = CategoryComboBox.SelectedItem?.ToString() ?? "Aktivitas";
        return selected.Trim().ToLowerInvariant() switch
        {
            "pembelajaran" => "pembelajaran",
            "kendala" => "kendala",
            _ => "aktivitas"
        };
    }

    private void UpdateCharCount()
    {
        var count = NoteTextBox.Text.Length;
        CharCountLabel.Text = $"{count} / 5000 karakter";
        if (count > 5000)
        {
            CharCountLabel.ForeColor = Color.FromArgb(220, 38, 38);
        }
        else
        {
            CharCountLabel.ForeColor = Color.FromArgb(100, 116, 139);
        }
    }

    public void SwitchToEditor()
    {
        OnSwitchToEditorRequested?.Invoke();
    }

    public async Task<bool> SubmitNoteAsync(string? workDate = null)
    {
        var targetDate = !string.IsNullOrWhiteSpace(workDate) ? workDate : _targetDate;
        var rawNote = NoteTextBox.Text;

        ErrorLabel.Visible = false;
        StatusLabel.Visible = false;

        if (!FallbackNoteHelper.IsValidNote(rawNote))
        {
            ErrorLabel.Text = "Catatan tidak boleh kosong atau melebihi 5000 karakter.";
            ErrorLabel.Visible = true;
            return false;
        }

        SendNoteButton.Enabled = false;
        SendNoteButton.Text = "Mengirim...";

        try
        {
            var req = new CreateNoteRequest
            {
                WorkDate = targetDate,
                Category = GetSelectedCategoryKey(),
                Note = rawNote.Trim()
            };

            var res = await _apiClient.PostNoteAsync(req);
            if (res != null && res.Success)
            {
                NoteTextBox.Text = string.Empty;
                StatusLabel.Text = "Catatan berhasil disimpan! Pipeline sedang diperbarui...";
                StatusLabel.Visible = true;
                OnNoteSubmitted?.Invoke();
                return true;
            }

            ErrorLabel.Text = "Gagal menyimpan catatan ke backend. Pastikan server aktif.";
            ErrorLabel.Visible = true;
            return false;
        }
        catch (Exception ex)
        {
            ErrorLabel.Text = $"Terjadi kesalahan: {ex.Message}";
            ErrorLabel.Visible = true;
            return false;
        }
        finally
        {
            SendNoteButton.Enabled = true;
            SendNoteButton.Text = "Kirim Catatan 🚀";
        }
    }
}
