using System.Diagnostics;
using MagangLog.Desktop.Models;
using MagangLog.Desktop.Services;

namespace MagangLog.Desktop.Controls;

/// <summary>
/// Panel that renders the system requirements checklist, per-item status badges,
/// inline re-check buttons, and Windows installation/troubleshooting guides.
/// </summary>
public class RequirementListPanel : Panel
{
    private readonly BackendApiClient _apiClient;
    private readonly List<RequirementItem> _items = new();
    private readonly Panel _cardsContainer;
    private readonly Label _lblSummary;

    public bool AllRequirementsSatisfied => _items.Count > 0 && _items.All(i => i.Status == "ok");
    public int UnmetCount => _items.Count(i => i.Status != "ok");
    public IReadOnlyList<RequirementItem> Items => _items;

    public event EventHandler? GateStateChanged;

    public RequirementListPanel(BackendApiClient? apiClient = null)
    {
        _apiClient = apiClient ?? new BackendApiClient();

        Dock = DockStyle.Fill;
        AutoScroll = true;
        Padding = new Padding(8);
        BackColor = Color.White;

        _lblSummary = new Label
        {
            Dock = DockStyle.Top,
            Height = 28,
            Font = new Font(Font.FontFamily, 9.5f, FontStyle.Italic),
            ForeColor = Color.FromArgb(100, 116, 139),
            Text = "Memeriksa dependensi sistem..."
        };
        Controls.Add(_lblSummary);

        _cardsContainer = new Panel
        {
            Dock = DockStyle.Fill,
            AutoScroll = true
        };
        Controls.Add(_cardsContainer);
        _cardsContainer.BringToFront();
    }

    /// <summary>
    /// Fetch requirements list from backend and render visual items.
    /// </summary>
    public async Task LoadRequirementsAsync()
    {
        _lblSummary.Text = "Memindai requirement dari repository dan sistem...";
        try
        {
            var results = await _apiClient.GetRequirementsAsync();
            _items.Clear();
            _items.AddRange(results);

            RenderItems();
            NotifyGateState();
        }
        catch (Exception ex)
        {
            _lblSummary.Text = $"Gagal memuat requirement: {ex.Message}";
        }
    }

    /// <summary>
    /// Re-evaluates a single requirement by name and updates its visual state.
    /// </summary>
    public async Task RecheckItemAsync(string name)
    {
        Cursor = Cursors.WaitCursor;
        try
        {
            var updated = await _apiClient.RecheckRequirementAsync(name);
            if (updated != null)
            {
                var index = _items.FindIndex(i => i.Name.Equals(name, StringComparison.OrdinalIgnoreCase));
                if (index >= 0)
                {
                    _items[index] = updated;
                }
                else
                {
                    _items.Add(updated);
                }

                RenderItems();
                NotifyGateState();
            }
        }
        finally
        {
            Cursor = Cursors.Default;
        }
    }

    private void NotifyGateState()
    {
        if (AllRequirementsSatisfied)
        {
            _lblSummary.Text = "✅ Semua requirement sistem telah terpenuhi.";
            _lblSummary.ForeColor = Color.FromArgb(22, 101, 52);
        }
        else
        {
            _lblSummary.Text = $"⚠️ {UnmetCount} requirement belum terpenuhi. Silakan selesaikan panduan di bawah.";
            _lblSummary.ForeColor = Color.FromArgb(185, 28, 28);
        }

        GateStateChanged?.Invoke(this, EventArgs.Empty);
    }

    private void RenderItems()
    {
        _cardsContainer.Controls.Clear();
        _cardsContainer.SuspendLayout();

        // Render from bottom to top for DockStyle.Top stacking
        for (int i = _items.Count - 1; i >= 0; i--)
        {
            var item = _items[i];
            var card = CreateRequirementCard(item);
            _cardsContainer.Controls.Add(card);
        }

        _cardsContainer.ResumeLayout(true);
    }

    private Control CreateRequirementCard(RequirementItem item)
    {
        var card = new Panel
        {
            Dock = DockStyle.Top,
            AutoSize = true,
            BackColor = Color.FromArgb(248, 250, 252),
            Margin = new Padding(0, 0, 0, 12),
            Padding = new Padding(14)
        };

        // Header strip
        var header = new Panel
        {
            Dock = DockStyle.Top,
            Height = 36
        };

        var titleLabel = new Label
        {
            Text = $"{item.Name} ({item.MinVersion})",
            Font = new Font(Font.FontFamily, 10f, FontStyle.Bold),
            ForeColor = Color.FromArgb(15, 23, 42),
            Dock = DockStyle.Left,
            AutoSize = true,
            TextAlign = ContentAlignment.MiddleLeft
        };

        var badgeLabel = new Label
        {
            Dock = DockStyle.Left,
            AutoSize = true,
            Font = new Font(Font.FontFamily, 9f, FontStyle.Bold),
            TextAlign = ContentAlignment.MiddleLeft,
            Padding = new Padding(6, 4, 6, 4)
        };

        if (item.Status == "ok")
        {
            badgeLabel.Text = $"✅ Terpenuhi (v{item.InstalledVersion ?? "terinstal"})";
            badgeLabel.ForeColor = Color.FromArgb(22, 101, 52);
            badgeLabel.BackColor = Color.FromArgb(220, 252, 231);
        }
        else if (item.Status == "version_mismatch")
        {
            badgeLabel.Text = $"⚠️ Versi kurang (terinstal v{item.InstalledVersion}, butuh {item.MinVersion})";
            badgeLabel.ForeColor = Color.FromArgb(146, 64, 14);
            badgeLabel.BackColor = Color.FromArgb(254, 243, 199);
        }
        else
        {
            badgeLabel.Text = $"❌ Belum terinstal (butuh {item.MinVersion})";
            badgeLabel.ForeColor = Color.FromArgb(153, 27, 27);
            badgeLabel.BackColor = Color.FromArgb(254, 226, 226);
        }

        var btnRecheck = new Button
        {
            Text = "Cek Ulang",
            Dock = DockStyle.Right,
            Width = 90,
            Height = 28,
            BackColor = Color.White,
            ForeColor = Color.FromArgb(37, 99, 235),
            FlatStyle = FlatStyle.Flat,
            Font = new Font(Font.FontFamily, 8.5f, FontStyle.Regular),
            Cursor = Cursors.Hand
        };
        btnRecheck.FlatAppearance.BorderColor = Color.FromArgb(203, 213, 225);
        btnRecheck.Click += async (_, _) => await RecheckItemAsync(item.Name);

        header.Controls.Add(btnRecheck);
        header.Controls.Add(badgeLabel);
        header.Controls.Add(titleLabel);
        card.Controls.Add(header);

        // If not ok, render detailed Windows installation and troubleshooting guide
        if (item.Status != "ok" && item.Guidance != null)
        {
            var guidePanel = CreateGuidePanel(item.Guidance);
            card.Controls.Add(guidePanel);
            guidePanel.BringToFront();
        }

        return card;
    }

    private Control CreateGuidePanel(InstallationGuidance guidance)
    {
        var panel = new Panel
        {
            Dock = DockStyle.Top,
            AutoSize = true,
            BackColor = Color.White,
            Padding = new Padding(12),
            Margin = new Padding(0, 8, 0, 0)
        };

        var flow = new FlowLayoutPanel
        {
            Dock = DockStyle.Top,
            AutoSize = true,
            FlowDirection = FlowDirection.TopDown,
            WrapContents = false
        };

        // 1. Download link
        if (!string.IsNullOrEmpty(guidance.DownloadUrl))
        {
            var link = new LinkLabel
            {
                Text = $"🔗 Unduh Installer Windows Resmi: {guidance.DownloadUrl}",
                AutoSize = true,
                Font = new Font(Font.FontFamily, 9f, FontStyle.Regular),
                Margin = new Padding(0, 2, 0, 6),
                Cursor = Cursors.Hand
            };
            link.LinkClicked += (_, _) =>
            {
                try
                {
                    Process.Start(new ProcessStartInfo(guidance.DownloadUrl) { UseShellExecute = true });
                }
                catch
                {
                    // Fallback if browser launcher fails
                }
            };
            flow.Controls.Add(link);
        }

        // 2. Steps
        if (guidance.InstallSteps.Count > 0)
        {
            var stepsTitle = new Label
            {
                Text = "Langkah Instalasi:",
                Font = new Font(Font.FontFamily, 8.5f, FontStyle.Bold),
                ForeColor = Color.FromArgb(51, 65, 85),
                AutoSize = true,
                Margin = new Padding(0, 4, 0, 2)
            };
            flow.Controls.Add(stepsTitle);

            for (int s = 0; s < guidance.InstallSteps.Count; s++)
            {
                var stepLbl = new Label
                {
                    Text = $"  {s + 1}. {guidance.InstallSteps[s]}",
                    Font = new Font(Font.FontFamily, 8.5f, FontStyle.Regular),
                    ForeColor = Color.FromArgb(71, 85, 105),
                    AutoSize = true,
                    Margin = new Padding(0, 1, 0, 1)
                };
                flow.Controls.Add(stepLbl);
            }
        }

        // 3. Verification command
        if (!string.IsNullOrEmpty(guidance.VerificationCommand))
        {
            var verifyLbl = new Label
            {
                Text = $"Perintah Verifikasi: {guidance.VerificationCommand} (output diharapkan: {guidance.ExpectedOutput})",
                Font = new Font(Font.FontFamily, 8.5f, FontStyle.Italic),
                ForeColor = Color.FromArgb(30, 41, 59),
                AutoSize = true,
                Margin = new Padding(0, 6, 0, 4),
                BackColor = Color.FromArgb(241, 245, 249),
                Padding = new Padding(4)
            };
            flow.Controls.Add(verifyLbl);
        }

        // 4. Troubleshooting
        if (guidance.Troubleshooting.Count > 0)
        {
            var tipsTitle = new Label
            {
                Text = "Troubleshooting / Tips PATH:",
                Font = new Font(Font.FontFamily, 8.5f, FontStyle.Bold),
                ForeColor = Color.FromArgb(146, 64, 14),
                AutoSize = true,
                Margin = new Padding(0, 4, 0, 2)
            };
            flow.Controls.Add(tipsTitle);

            foreach (var tip in guidance.Troubleshooting)
            {
                var tipLbl = new Label
                {
                    Text = $"  • {tip}",
                    Font = new Font(Font.FontFamily, 8.5f, FontStyle.Regular),
                    ForeColor = Color.FromArgb(100, 116, 139),
                    AutoSize = true,
                    Margin = new Padding(0, 1, 0, 1)
                };
                flow.Controls.Add(tipLbl);
            }
        }

        panel.Controls.Add(flow);
        return panel;
    }
}

