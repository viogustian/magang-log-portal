using MagangLog.Desktop.Models;
using MagangLog.Desktop.Services;

namespace MagangLog.Desktop.Controls;

/// <summary>
/// Panel that manages project work directories selection, backend path validation,
/// Git repository badge detection, and item removal.
/// </summary>
public class FolderListPanel : Panel
{
    private readonly BackendApiClient _apiClient;
    private readonly List<FolderValidationResult> _folders = new();
    private readonly Panel _listContainer;
    private readonly TextBox _txtManualPath;
    private readonly Label _lblSummary;

    public IReadOnlyList<FolderValidationResult> Folders => _folders;
    public bool HasValidFolders => _folders.Any(f => f.IsValid);
    public int ValidFolderCount => _folders.Count(f => f.IsValid);

    public event EventHandler? GateStateChanged;

    public FolderListPanel(BackendApiClient? apiClient = null)
    {
        _apiClient = apiClient ?? new BackendApiClient();

        Dock = DockStyle.Fill;
        Padding = new Padding(8);
        BackColor = Color.White;

        // Top bar: Add Folder Button + Manual Path Fallback Input
        var topBar = new Panel
        {
            Dock = DockStyle.Top,
            Height = 44,
            Padding = new Padding(0, 0, 0, 8)
        };

        var btnBrowse = new Button
        {
            Text = "📁 Tambah Folder",
            Dock = DockStyle.Left,
            Width = 140,
            Height = 36,
            BackColor = Color.FromArgb(37, 99, 235),
            ForeColor = Color.White,
            FlatStyle = FlatStyle.Flat,
            Font = new Font(Font.FontFamily, 9f, FontStyle.Bold),
            Cursor = Cursors.Hand
        };
        btnBrowse.FlatAppearance.BorderSize = 0;
        btnBrowse.Click += async (_, _) => await HandleBrowseClickAsync();

        _txtManualPath = new TextBox
        {
            Dock = DockStyle.Fill,
            Font = new Font(Font.FontFamily, 9.5f, FontStyle.Regular),
            PlaceholderText = "Atau masukkan / tempel path folder lengkap di sini..."
        };

        var btnAddManual = new Button
        {
            Text = "Tambah",
            Dock = DockStyle.Right,
            Width = 80,
            Height = 36,
            BackColor = Color.FromArgb(241, 245, 249),
            ForeColor = Color.FromArgb(51, 65, 85),
            FlatStyle = FlatStyle.Flat,
            Font = new Font(Font.FontFamily, 9f, FontStyle.Regular),
            Cursor = Cursors.Hand
        };
        btnAddManual.FlatAppearance.BorderColor = Color.FromArgb(203, 213, 225);
        btnAddManual.Click += async (_, _) =>
        {
            var p = _txtManualPath.Text.Trim();
            if (!string.IsNullOrEmpty(p))
            {
                await AddFolderAsync(p);
                _txtManualPath.Text = string.Empty;
            }
        };

        var inputWrap = new Panel
        {
            Dock = DockStyle.Fill,
            Padding = new Padding(12, 4, 12, 4)
        };
        inputWrap.Controls.Add(_txtManualPath);

        topBar.Controls.Add(inputWrap);
        topBar.Controls.Add(btnAddManual);
        topBar.Controls.Add(btnBrowse);
        Controls.Add(topBar);

        _lblSummary = new Label
        {
            Dock = DockStyle.Top,
            Height = 26,
            Font = new Font(Font.FontFamily, 9f, FontStyle.Italic),
            ForeColor = Color.FromArgb(100, 116, 139),
            Text = "Pilih minimal satu folder proyek lokal untuk dipantau."
        };
        Controls.Add(_lblSummary);

        _listContainer = new Panel
        {
            Dock = DockStyle.Fill,
            AutoScroll = true,
            Padding = new Padding(0, 4, 0, 0)
        };
        Controls.Add(_listContainer);
        _listContainer.BringToFront();
    }

    private async Task HandleBrowseClickAsync()
    {
        using var dlg = new FolderBrowserDialog
        {
            Description = "Pilih folder proyek kerja Anda",
            UseDescriptionForTitle = true,
            ShowNewFolderButton = false
        };

        if (dlg.ShowDialog(FindForm()) == DialogResult.OK && !string.IsNullOrWhiteSpace(dlg.SelectedPath))
        {
            await AddFolderAsync(dlg.SelectedPath);
        }
    }

    /// <summary>
    /// Validates and adds a folder path into the active list.
    /// </summary>
    public async Task AddFolderAsync(string folderPath)
    {
        var cleanPath = folderPath.Trim();
        if (string.IsNullOrWhiteSpace(cleanPath))
        {
            return;
        }

        Cursor = Cursors.WaitCursor;
        try
        {
            var results = await _apiClient.ValidateFoldersAsync(new[] { cleanPath });
            var result = results.FirstOrDefault() ?? new FolderValidationResult
            {
                Path = cleanPath,
                Exists = false,
                Readable = false,
                IsGit = false,
                Error = "Folder tidak ditemukan"
            };

            // Remove existing duplicate if path was already present
            _folders.RemoveAll(f => f.Path.Equals(result.Path, StringComparison.OrdinalIgnoreCase)
                                 || f.Path.Equals(cleanPath, StringComparison.OrdinalIgnoreCase));
            _folders.Add(result);

            RenderItems();
            NotifyGateState();
        }
        finally
        {
            Cursor = Cursors.Default;
        }
    }

    /// <summary>
    /// Remove folder from list.
    /// </summary>
    public void RemoveFolder(string folderPath)
    {
        _folders.RemoveAll(f => f.Path.Equals(folderPath, StringComparison.OrdinalIgnoreCase));
        RenderItems();
        NotifyGateState();
    }

    /// <summary>
    /// Bulk load saved folder paths.
    /// </summary>
    public async Task LoadFoldersAsync(IEnumerable<string> paths)
    {
        var list = paths.Where(p => !string.IsNullOrWhiteSpace(p)).ToList();
        if (list.Count == 0)
        {
            return;
        }

        try
        {
            var results = await _apiClient.ValidateFoldersAsync(list);
            _folders.Clear();
            _folders.AddRange(results);
            RenderItems();
            NotifyGateState();
        }
        catch
        {
            // Fallback: add items as missing
            foreach (var p in list)
            {
                _folders.Add(new FolderValidationResult { Path = p, Exists = false, Error = "Belum divalidasi" });
            }
            RenderItems();
            NotifyGateState();
        }
    }

    public List<string> GetValidFolderPaths()
    {
        return _folders.Where(f => f.IsValid).Select(f => f.Path).ToList();
    }

    private void NotifyGateState()
    {
        if (HasValidFolders)
        {
            _lblSummary.Text = $"✅ {ValidFolderCount} folder proyek valid terdaftar.";
            _lblSummary.ForeColor = Color.FromArgb(22, 101, 52);
        }
        else
        {
            _lblSummary.Text = "⚠️ Minimal satu folder proyek valid harus ditambahkan untuk melanjutkan.";
            _lblSummary.ForeColor = Color.FromArgb(185, 28, 28);
        }

        GateStateChanged?.Invoke(this, EventArgs.Empty);
    }

    private void RenderItems()
    {
        _listContainer.Controls.Clear();
        _listContainer.SuspendLayout();

        for (int i = _folders.Count - 1; i >= 0; i--)
        {
            var item = _folders[i];
            var card = CreateFolderCard(item);
            _listContainer.Controls.Add(card);
        }

        _listContainer.ResumeLayout(true);
    }

    private Control CreateFolderCard(FolderValidationResult item)
    {
        var card = new Panel
        {
            Dock = DockStyle.Top,
            Height = 48,
            BackColor = Color.FromArgb(248, 250, 252),
            Margin = new Padding(0, 0, 0, 8),
            Padding = new Padding(12, 8, 12, 8)
        };

        var btnRemove = new Button
        {
            Text = "✕",
            Dock = DockStyle.Right,
            Width = 32,
            Height = 32,
            BackColor = Color.Transparent,
            ForeColor = Color.FromArgb(153, 27, 27),
            FlatStyle = FlatStyle.Flat,
            Font = new Font(Font.FontFamily, 9.5f, FontStyle.Bold),
            Cursor = Cursors.Hand
        };
        btnRemove.FlatAppearance.BorderSize = 0;
        btnRemove.Click += (_, _) => RemoveFolder(item.Path);

        var gitBadge = new Label
        {
            Dock = DockStyle.Right,
            AutoSize = true,
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Bold),
            TextAlign = ContentAlignment.MiddleCenter,
            Padding = new Padding(6, 4, 6, 4)
        };

        if (item.IsGit)
        {
            gitBadge.Text = "🔀 Git repo";
            gitBadge.ForeColor = Color.FromArgb(30, 64, 175);
            gitBadge.BackColor = Color.FromArgb(219, 234, 254);
        }
        else
        {
            gitBadge.Text = "📁 Non-Git";
            gitBadge.ForeColor = Color.FromArgb(100, 116, 139);
            gitBadge.BackColor = Color.FromArgb(241, 245, 249);
        }

        var statusBadge = new Label
        {
            Dock = DockStyle.Right,
            AutoSize = true,
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Bold),
            TextAlign = ContentAlignment.MiddleCenter,
            Padding = new Padding(6, 4, 6, 4),
            Margin = new Padding(0, 0, 6, 0)
        };

        if (item.IsValid)
        {
            statusBadge.Text = "✅ Siap";
            statusBadge.ForeColor = Color.FromArgb(22, 101, 52);
            statusBadge.BackColor = Color.FromArgb(220, 252, 231);
        }
        else
        {
            statusBadge.Text = $"❌ {item.Error ?? "Tidak valid"}";
            statusBadge.ForeColor = Color.FromArgb(153, 27, 27);
            statusBadge.BackColor = Color.FromArgb(254, 226, 226);
        }

        var pathLabel = new Label
        {
            Text = item.Path,
            Font = new Font(Font.FontFamily, 9f, FontStyle.Regular),
            ForeColor = Color.FromArgb(15, 23, 42),
            Dock = DockStyle.Fill,
            TextAlign = ContentAlignment.MiddleLeft,
            AutoEllipsis = true
        };

        card.Controls.Add(pathLabel);
        card.Controls.Add(statusBadge);
        card.Controls.Add(gitBadge);
        card.Controls.Add(btnRemove);

        return card;
    }
}
