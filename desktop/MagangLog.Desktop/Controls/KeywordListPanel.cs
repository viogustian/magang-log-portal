using System.Drawing;
using System.Windows.Forms;

namespace MagangLog.Desktop.Controls;

/// <summary>
/// Panel for reviewing and editing the canonical job profile name and application detection keywords
/// (process names and window title keywords).
/// </summary>
public class KeywordListPanel : Panel
{
    private readonly List<string> _keywords = new();
    private readonly TextBox _txtProfileName;
    private readonly FlowLayoutPanel _listContainer;
    private readonly TextBox _txtNewKeyword;
    private readonly Button _btnAddKeyword;

    public string ProfileName
    {
        get => _txtProfileName.Text.Trim();
        set => _txtProfileName.Text = value ?? string.Empty;
    }

    public IReadOnlyList<string> Keywords => _keywords.AsReadOnly();

    public event EventHandler? KeywordsChanged;

    public KeywordListPanel()
    {
        Dock = DockStyle.Fill;
        BackColor = Color.White;
        Padding = new Padding(0);

        // Top: Profile name input row
        var profileRow = new Panel
        {
            Dock = DockStyle.Top,
            Height = 44,
            Padding = new Padding(0, 0, 0, 6)
        };

        var lblProfile = new Label
        {
            Text = "Nama Profil:",
            Dock = DockStyle.Left,
            Width = 90,
            TextAlign = ContentAlignment.MiddleLeft,
            Font = new Font(Font.FontFamily, 9f, FontStyle.Bold),
            ForeColor = Color.FromArgb(51, 65, 85)
        };

        _txtProfileName = new TextBox
        {
            Dock = DockStyle.Fill,
            Font = new Font(Font.FontFamily, 9.5f, FontStyle.Regular),
            PlaceholderText = "Misal: Software Engineer, UI/UX Designer, Data Analyst..."
        };
        _txtProfileName.TextChanged += (_, _) => KeywordsChanged?.Invoke(this, EventArgs.Empty);

        var txtProfileWrap = new Panel
        {
            Dock = DockStyle.Fill,
            Padding = new Padding(0, 4, 0, 4)
        };
        txtProfileWrap.Controls.Add(_txtProfileName);

        profileRow.Controls.Add(txtProfileWrap);
        profileRow.Controls.Add(lblProfile);

        // Action row: Add new keyword
        var addRow = new Panel
        {
            Dock = DockStyle.Bottom,
            Height = 42,
            Padding = new Padding(0, 6, 0, 0)
        };

        _txtNewKeyword = new TextBox
        {
            Dock = DockStyle.Fill,
            Font = new Font(Font.FontFamily, 9.5f, FontStyle.Regular),
            PlaceholderText = "Tambah kata kunci baru (mis. Code.exe, Photoshop, devenv)..."
        };

        _btnAddKeyword = new Button
        {
            Text = "+ Tambah",
            Dock = DockStyle.Right,
            Width = 90,
            Height = 32,
            BackColor = Color.FromArgb(241, 245, 249),
            ForeColor = Color.FromArgb(30, 41, 59),
            FlatStyle = FlatStyle.Flat,
            Font = new Font(Font.FontFamily, 9f, FontStyle.Bold),
            Cursor = Cursors.Hand
        };
        _btnAddKeyword.FlatAppearance.BorderColor = Color.FromArgb(203, 213, 225);
        _btnAddKeyword.Click += (_, _) =>
        {
            var text = _txtNewKeyword.Text.Trim();
            if (!string.IsNullOrEmpty(text))
            {
                AddKeyword(text);
                _txtNewKeyword.Text = string.Empty;
            }
        };

        _txtNewKeyword.KeyDown += (_, e) =>
        {
            if (e.KeyCode == Keys.Enter)
            {
                e.SuppressKeyPress = true;
                _btnAddKeyword.PerformClick();
            }
        };

        var txtNewWrap = new Panel
        {
            Dock = DockStyle.Fill,
            Padding = new Padding(0, 2, 8, 2)
        };
        txtNewWrap.Controls.Add(_txtNewKeyword);

        addRow.Controls.Add(txtNewWrap);
        addRow.Controls.Add(_btnAddKeyword);

        // Header for keywords list
        var headerRow = new Panel
        {
            Dock = DockStyle.Top,
            Height = 24,
            Padding = new Padding(0, 2, 0, 2)
        };

        var lblKeywords = new Label
        {
            Text = "Kata Kunci Terdeteksi (Proses & Judul Jendela):",
            Dock = DockStyle.Fill,
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Bold),
            ForeColor = Color.FromArgb(100, 116, 139)
        };
        headerRow.Controls.Add(lblKeywords);

        // Flow container for keywords chips/cards
        _listContainer = new FlowLayoutPanel
        {
            Dock = DockStyle.Fill,
            AutoScroll = true,
            FlowDirection = FlowDirection.LeftToRight,
            WrapContents = true,
            BackColor = Color.FromArgb(248, 250, 252),
            BorderStyle = BorderStyle.FixedSingle,
            Padding = new Padding(6)
        };

        // Layout assembly (Bottom to Top order for Dock)
        Controls.Add(_listContainer);
        Controls.Add(headerRow);
        Controls.Add(addRow);
        Controls.Add(profileRow);
    }

    /// <summary>
    /// Sets the canonical profile name and populates the keyword items.
    /// </summary>
    public void SetProfile(string profileName, IEnumerable<string> keywords)
    {
        _txtProfileName.Text = profileName ?? string.Empty;
        _keywords.Clear();
        if (keywords != null)
        {
            foreach (var kw in keywords)
            {
                var trimmed = kw?.Trim();
                if (!string.IsNullOrEmpty(trimmed) && !_keywords.Contains(trimmed, StringComparer.OrdinalIgnoreCase))
                {
                    _keywords.Add(trimmed);
                }
            }
        }
        RebuildKeywordChips();
        KeywordsChanged?.Invoke(this, EventArgs.Empty);
    }

    /// <summary>
    /// Adds a single keyword item if not already present.
    /// </summary>
    public void AddKeyword(string keyword)
    {
        var trimmed = keyword?.Trim();
        if (string.IsNullOrEmpty(trimmed))
        {
            return;
        }

        if (!_keywords.Contains(trimmed, StringComparer.OrdinalIgnoreCase))
        {
            _keywords.Add(trimmed);
            RebuildKeywordChips();
            KeywordsChanged?.Invoke(this, EventArgs.Empty);
        }
    }

    /// <summary>
    /// Removes a keyword item by exact or case-insensitive match.
    /// </summary>
    public void RemoveKeyword(string keyword)
    {
        var idx = _keywords.FindIndex(k => string.Equals(k, keyword, StringComparison.OrdinalIgnoreCase));
        if (idx >= 0)
        {
            _keywords.RemoveAt(idx);
            RebuildKeywordChips();
            KeywordsChanged?.Invoke(this, EventArgs.Empty);
        }
    }

    /// <summary>
    /// Updates a keyword at a specific index.
    /// </summary>
    public void UpdateKeyword(int index, string newKeyword)
    {
        if (index >= 0 && index < _keywords.Count)
        {
            var trimmed = newKeyword?.Trim();
            if (!string.IsNullOrEmpty(trimmed))
            {
                _keywords[index] = trimmed;
                RebuildKeywordChips();
                KeywordsChanged?.Invoke(this, EventArgs.Empty);
            }
        }
    }

    private void RebuildKeywordChips()
    {
        _listContainer.SuspendLayout();
        _listContainer.Controls.Clear();

        for (int i = 0; i < _keywords.Count; i++)
        {
            var index = i;
            var keyword = _keywords[i];

            var chip = new Panel
            {
                AutoSize = true,
                AutoSizeMode = AutoSizeMode.GrowAndShrink,
                Height = 32,
                BackColor = Color.White,
                Margin = new Padding(4),
                Padding = new Padding(4, 2, 4, 2),
                BorderStyle = BorderStyle.FixedSingle
            };

            var txtInline = new TextBox
            {
                Text = keyword,
                Font = new Font(Font.FontFamily, 9f, FontStyle.Regular),
                BorderStyle = BorderStyle.None,
                BackColor = Color.White,
                Width = Math.Max(70, TextRenderer.MeasureText(keyword, new Font(Font.FontFamily, 9f)).Width + 14),
                Location = new Point(4, 5)
            };

            txtInline.TextChanged += (_, _) =>
            {
                txtInline.Width = Math.Max(70, TextRenderer.MeasureText(txtInline.Text, txtInline.Font).Width + 14);
            };

            txtInline.LostFocus += (_, _) =>
            {
                var val = txtInline.Text.Trim();
                if (!string.IsNullOrEmpty(val) && val != _keywords[index])
                {
                    _keywords[index] = val;
                    KeywordsChanged?.Invoke(this, EventArgs.Empty);
                }
            };

            var btnDelete = new Button
            {
                Text = "✕",
                Width = 22,
                Height = 22,
                Location = new Point(txtInline.Right + 2, 4),
                FlatStyle = FlatStyle.Flat,
                ForeColor = Color.FromArgb(148, 163, 184),
                Font = new Font(Font.FontFamily, 8f, FontStyle.Bold),
                Cursor = Cursors.Hand
            };
            btnDelete.FlatAppearance.BorderSize = 0;
            btnDelete.Click += (_, _) =>
            {
                RemoveKeyword(keyword);
            };

            chip.Controls.Add(txtInline);
            chip.Controls.Add(btnDelete);
            _listContainer.Controls.Add(chip);
        }

        _listContainer.ResumeLayout();
    }
}
