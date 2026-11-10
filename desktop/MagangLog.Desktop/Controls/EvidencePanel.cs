using System.Drawing;
using MagangLog.Desktop.Models;

namespace MagangLog.Desktop.Controls;

/// <summary>
/// Right-hand timeline feed displaying today's immutable evidence records.
/// Features a DataGridView, instant client-side source filtering, and strength-based cell highlighting.
/// </summary>
public class EvidencePanel : Panel
{
    private readonly List<EvidenceItem> _allItems = new();

    public ComboBox FilterSourceComboBox { get; }
    public DataGridView EvidenceGrid { get; }
    public Label EmptyPlaceholderLabel { get; }

    public IReadOnlyList<EvidenceItem> AllItems => _allItems.AsReadOnly();

    public EvidencePanel()
    {
        Dock = DockStyle.Fill;
        BackColor = Color.White;
        Padding = new Padding(16, 12, 16, 12);

        // 1. Header & Filter Bar
        var topPanel = new Panel
        {
            Dock = DockStyle.Top,
            Height = 44,
            BackColor = Color.Transparent
        };

        var lblTitle = new Label
        {
            Text = "Bukti Hari Ini (Evidence Feed)",
            Font = new Font(Font.FontFamily, 10.5f, FontStyle.Bold),
            ForeColor = Color.FromArgb(15, 23, 42),
            Dock = DockStyle.Left,
            AutoSize = true,
            TextAlign = ContentAlignment.MiddleLeft,
            Padding = new Padding(0, 8, 0, 0)
        };

        var filterFlow = new FlowLayoutPanel
        {
            Dock = DockStyle.Right,
            FlowDirection = FlowDirection.RightToLeft,
            AutoSize = true,
            BackColor = Color.Transparent,
            WrapContents = false,
            Padding = new Padding(0, 4, 0, 0)
        };

        FilterSourceComboBox = new ComboBox
        {
            DropDownStyle = ComboBoxStyle.DropDownList,
            Width = 110,
            Font = new Font(Font.FontFamily, 9f, FontStyle.Regular),
            Cursor = Cursors.Hand
        };
        FilterSourceComboBox.Items.AddRange(new object[] { "Semua", "Git", "App", "Browser", "Notes" });
        FilterSourceComboBox.SelectedIndex = 0;
        FilterSourceComboBox.SelectedIndexChanged += (_, _) => ApplyFilter();

        var lblFilter = new Label
        {
            Text = "Filter:",
            Font = new Font(Font.FontFamily, 9f, FontStyle.Regular),
            ForeColor = Color.FromArgb(71, 85, 105),
            AutoSize = true,
            Margin = new Padding(0, 6, 4, 0)
        };

        filterFlow.Controls.Add(FilterSourceComboBox);
        filterFlow.Controls.Add(lblFilter);

        topPanel.Controls.Add(lblTitle);
        topPanel.Controls.Add(filterFlow);

        // 2. DataGridView for Evidence Items
        EvidenceGrid = new DataGridView
        {
            Dock = DockStyle.Fill,
            ReadOnly = true,
            AllowUserToAddRows = false,
            AllowUserToDeleteRows = false,
            AllowUserToResizeRows = false,
            SelectionMode = DataGridViewSelectionMode.FullRowSelect,
            MultiSelect = false,
            RowHeadersVisible = false,
            BackgroundColor = Color.White,
            BorderStyle = BorderStyle.None,
            CellBorderStyle = DataGridViewCellBorderStyle.SingleHorizontal,
            GridColor = Color.FromArgb(241, 245, 249),
            EnableHeadersVisualStyles = false,
            AutoGenerateColumns = false
        };

        EvidenceGrid.ColumnHeadersDefaultCellStyle.BackColor = Color.FromArgb(248, 250, 252);
        EvidenceGrid.ColumnHeadersDefaultCellStyle.ForeColor = Color.FromArgb(71, 85, 105);
        EvidenceGrid.ColumnHeadersDefaultCellStyle.Font = new Font(Font.FontFamily, 9f, FontStyle.Bold);
        EvidenceGrid.ColumnHeadersHeight = 32;

        var colTime = new DataGridViewTextBoxColumn
        {
            HeaderText = "Waktu",
            Name = "colTime",
            Width = 65,
            ReadOnly = true,
            DefaultCellStyle = { Alignment = DataGridViewContentAlignment.MiddleCenter }
        };
        var colSource = new DataGridViewTextBoxColumn
        {
            HeaderText = "Sumber",
            Name = "colSource",
            Width = 95,
            ReadOnly = true
        };
        var colTitle = new DataGridViewTextBoxColumn
        {
            HeaderText = "Judul",
            Name = "colTitle",
            AutoSizeMode = DataGridViewAutoSizeColumnMode.Fill,
            ReadOnly = true
        };
        var colStrength = new DataGridViewTextBoxColumn
        {
            HeaderText = "Kekuatan",
            Name = "colStrength",
            Width = 80,
            ReadOnly = true,
            DefaultCellStyle = { Alignment = DataGridViewContentAlignment.MiddleCenter }
        };

        EvidenceGrid.Columns.Add(colTime);
        EvidenceGrid.Columns.Add(colSource);
        EvidenceGrid.Columns.Add(colTitle);
        EvidenceGrid.Columns.Add(colStrength);

        EvidenceGrid.CellFormatting += (s, e) =>
        {
            if (e.RowIndex >= 0 && e.ColumnIndex == 3 && e.CellStyle != null)
            {
                TriggerCellFormatting(e.RowIndex, e.ColumnIndex, e.Value, e.CellStyle);
            }
        };

        // 3. Empty Placeholder Label
        EmptyPlaceholderLabel = new Label
        {
            Text = "Belum ada aktivitas terekam hari ini",
            Font = new Font(Font.FontFamily, 9.5f, FontStyle.Regular),
            ForeColor = Color.FromArgb(100, 116, 139),
            Dock = DockStyle.Fill,
            TextAlign = ContentAlignment.MiddleCenter,
            Visible = true
        };

        // Controls container
        var contentPanel = new Panel
        {
            Dock = DockStyle.Fill,
            BackColor = Color.Transparent
        };
        contentPanel.Controls.Add(EmptyPlaceholderLabel);
        contentPanel.Controls.Add(EvidenceGrid);

        Controls.Add(contentPanel);
        Controls.Add(topPanel);
    }

    /// <summary>
    /// Populate evidence items feed from backend data and apply current filter.
    /// </summary>
    public void SetEvidenceItems(IEnumerable<EvidenceItem>? items)
    {
        _allItems.Clear();
        if (items != null)
        {
            _allItems.AddRange(items);
        }

        ApplyFilter();
    }

    /// <summary>
    /// Apply active client-side category filter to the DataGridView rows.
    /// </summary>
    public void ApplyFilter()
    {
        EvidenceGrid.Rows.Clear();

        var selectedFilter = FilterSourceComboBox.SelectedItem?.ToString() ?? "Semua";
        var filtered = EvidenceHelper.FilterItems(_allItems, selectedFilter);

        foreach (var item in filtered)
        {
            var rowIndex = EvidenceGrid.Rows.Add(
                EvidenceHelper.FormatTime(item.Timestamp),
                EvidenceHelper.GetSourceBadge(item.Source),
                item.Title,
                item.Strength
            );
            EvidenceGrid.Rows[rowIndex].Tag = item;
        }

        var hasRows = EvidenceGrid.Rows.Count > 0;
        EvidenceGrid.Visible = hasRows;
        EmptyPlaceholderLabel.Visible = !hasRows;
    }

    /// <summary>
    /// Format strength cell background and text styling.
    /// </summary>
    public void TriggerCellFormatting(int row, int col, object? value, DataGridViewCellStyle cellStyle)
    {
        var strengthStr = value?.ToString();
        var color = EvidenceHelper.GetStrengthColor(strengthStr);
        cellStyle.BackColor = color;

        if (string.Equals(strengthStr, "strong", StringComparison.OrdinalIgnoreCase))
        {
            cellStyle.ForeColor = Color.FromArgb(20, 83, 45);
        }
        else
        {
            cellStyle.ForeColor = Color.FromArgb(113, 63, 18);
        }
    }
}
