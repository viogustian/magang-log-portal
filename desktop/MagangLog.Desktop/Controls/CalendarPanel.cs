using System.Drawing;
using MagangLog.Desktop.Models;
using MagangLog.Desktop.Services;

namespace MagangLog.Desktop.Controls;

/// <summary>
/// Monthly visual calendar panel for Kemnaker Monev compliance monitoring,
/// with 7-column weekday matrix (Mon-Sun), status color coding, and month navigation.
/// </summary>
public class CalendarPanel : Panel
{
    private readonly BackendApiClient _apiClient;

    public int CurrentYear { get; private set; }
    public int CurrentMonth { get; private set; }
    public MonthCalendarResponse? CurrentData { get; private set; }
    public List<CalendarDayCellModel[]> CurrentMatrix { get; private set; } = new();

    public Button PrevMonthButton { get; }
    public Button NextMonthButton { get; }
    public Label MonthTitleLabel { get; }
    public DataGridView CalendarGrid { get; }

    public event Action<CalendarDayCellModel>? OnDaySelected;
    public event Action<int, int>? OnMonthChanged;

    public CalendarPanel(BackendApiClient? apiClient = null)
    {
        _apiClient = apiClient ?? new BackendApiClient();

        Dock = DockStyle.Fill;
        BackColor = Color.White;
        Padding = new Padding(16, 8, 16, 8);

        // Header Panel (Nav buttons, month title, and status legends)
        var headerPanel = new Panel
        {
            Dock = DockStyle.Top,
            Height = 36,
            BackColor = Color.Transparent
        };

        var navFlow = new FlowLayoutPanel
        {
            Dock = DockStyle.Left,
            FlowDirection = FlowDirection.LeftToRight,
            AutoSize = true,
            BackColor = Color.Transparent,
            WrapContents = false
        };

        var lblCalendarTitle = new Label
        {
            Text = "Kalender Monev Kemnaker",
            Font = new Font("Segoe UI", 10.5f, FontStyle.Bold),
            ForeColor = Color.FromArgb(15, 23, 42),
            AutoSize = true,
            TextAlign = ContentAlignment.MiddleLeft,
            Margin = new Padding(0, 4, 16, 0)
        };
        navFlow.Controls.Add(lblCalendarTitle);

        PrevMonthButton = new Button
        {
            Text = "◀",
            Width = 32,
            Height = 26,
            FlatStyle = FlatStyle.Flat,
            Font = new Font("Segoe UI", 8.5f, FontStyle.Bold),
            BackColor = Color.FromArgb(241, 245, 249),
            ForeColor = Color.FromArgb(30, 41, 59),
            Cursor = Cursors.Hand,
            Margin = new Padding(0, 2, 4, 0)
        };
        PrevMonthButton.FlatAppearance.BorderColor = Color.FromArgb(203, 213, 225);
        PrevMonthButton.Click += async (s, e) => await NavigatePrevMonthAsync();
        navFlow.Controls.Add(PrevMonthButton);

        MonthTitleLabel = new Label
        {
            Text = "Oktober 2026",
            Font = new Font("Segoe UI", 9.5f, FontStyle.Bold),
            ForeColor = Color.FromArgb(15, 23, 42),
            AutoSize = true,
            TextAlign = ContentAlignment.MiddleCenter,
            Margin = new Padding(4, 5, 4, 0)
        };
        navFlow.Controls.Add(MonthTitleLabel);

        NextMonthButton = new Button
        {
            Text = "▶",
            Width = 32,
            Height = 26,
            FlatStyle = FlatStyle.Flat,
            Font = new Font("Segoe UI", 8.5f, FontStyle.Bold),
            BackColor = Color.FromArgb(241, 245, 249),
            ForeColor = Color.FromArgb(30, 41, 59),
            Cursor = Cursors.Hand,
            Margin = new Padding(4, 2, 0, 0)
        };
        NextMonthButton.FlatAppearance.BorderColor = Color.FromArgb(203, 213, 225);
        NextMonthButton.Click += async (s, e) => await NavigateNextMonthAsync();
        navFlow.Controls.Add(NextMonthButton);

        // Legend Flow (Right side)
        var legendFlow = new FlowLayoutPanel
        {
            Dock = DockStyle.Right,
            FlowDirection = FlowDirection.LeftToRight,
            AutoSize = true,
            BackColor = Color.Transparent,
            WrapContents = false,
            Margin = new Padding(0, 4, 0, 0)
        };
        legendFlow.Controls.Add(CreateLegendBadge("🟢 Terkirim", Color.FromArgb(22, 101, 52)));
        legendFlow.Controls.Add(CreateLegendBadge("🟡 Perlu Input", Color.FromArgb(133, 77, 14)));
        legendFlow.Controls.Add(CreateLegendBadge("⚪ Libur/Akhir Pekan", Color.FromArgb(71, 85, 105)));
        legendFlow.Controls.Add(CreateLegendBadge("🔴 Terkunci", Color.FromArgb(153, 27, 27)));

        headerPanel.Controls.Add(navFlow);
        headerPanel.Controls.Add(legendFlow);
        Controls.Add(headerPanel);

        // Calendar DataGridView
        CalendarGrid = new DataGridView
        {
            Dock = DockStyle.Fill,
            ReadOnly = true,
            AllowUserToAddRows = false,
            AllowUserToDeleteRows = false,
            AllowUserToResizeRows = false,
            AllowUserToResizeColumns = false,
            RowHeadersVisible = false,
            SelectionMode = DataGridViewSelectionMode.CellSelect,
            MultiSelect = false,
            BackgroundColor = Color.White,
            BorderStyle = BorderStyle.None,
            AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill,
            EnableHeadersVisualStyles = false
        };

        CalendarGrid.ColumnHeadersDefaultCellStyle = new DataGridViewCellStyle
        {
            Alignment = DataGridViewContentAlignment.MiddleCenter,
            BackColor = Color.FromArgb(241, 245, 249),
            ForeColor = Color.FromArgb(51, 65, 85),
            Font = new Font("Segoe UI", 9f, FontStyle.Bold),
            SelectionBackColor = Color.FromArgb(241, 245, 249),
            SelectionForeColor = Color.FromArgb(51, 65, 85)
        };
        CalendarGrid.ColumnHeadersHeight = 26;

        var colNames = new[] { "Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min" };
        foreach (var colName in colNames)
        {
            var col = new DataGridViewTextBoxColumn
            {
                HeaderText = colName,
                ReadOnly = true,
                SortMode = DataGridViewColumnSortMode.NotSortable,
                DefaultCellStyle = new DataGridViewCellStyle
                {
                    Alignment = DataGridViewContentAlignment.MiddleCenter,
                    Font = new Font("Segoe UI", 9f, FontStyle.Regular),
                    SelectionBackColor = Color.FromArgb(219, 234, 254),
                    SelectionForeColor = Color.FromArgb(15, 23, 42)
                }
            };
            CalendarGrid.Columns.Add(col);
        }

        CalendarGrid.CellFormatting += OnCellFormatting;
        CalendarGrid.CellClick += OnCellClick;
        CalendarGrid.CellDoubleClick += OnCellClick;

        Controls.Add(CalendarGrid);

        // Initialize with current month
        var now = DateTime.Today;
        SetMonth(now.Year, now.Month);
    }

    private static Label CreateLegendBadge(string text, Color color)
    {
        return new Label
        {
            Text = text,
            Font = new Font("Segoe UI", 8.25f, FontStyle.Regular),
            ForeColor = color,
            AutoSize = true,
            Margin = new Padding(6, 6, 4, 0)
        };
    }

    public void SetMonth(int year, int month, MonthCalendarResponse? data = null)
    {
        CurrentYear = year;
        CurrentMonth = month;
        CurrentData = data;

        MonthTitleLabel.Text = GetMonthTitle(year, month);
        CurrentMatrix = CalendarGridBuilder.BuildMonthMatrix(year, month, data?.Days);

        CalendarGrid.RowCount = CurrentMatrix.Count;
        for (int r = 0; r < CurrentMatrix.Count; r++)
        {
            CalendarGrid.Rows[r].Height = 26;
            for (int c = 0; c < 7; c++)
            {
                var cellModel = CurrentMatrix[r][c];
                CalendarGrid.Rows[r].Cells[c].Value = cellModel.DayNumber?.ToString() ?? string.Empty;
            }
        }
        CalendarGrid.Invalidate();
    }

    public Color GetCellBackgroundColor(int row, int col)
    {
        if (row < 0 || row >= CurrentMatrix.Count || col < 0 || col >= 7)
        {
            return Color.White;
        }

        var cellModel = CurrentMatrix[row][col];
        if (!cellModel.DayNumber.HasValue)
        {
            return Color.FromArgb(248, 250, 252);
        }

        return CalendarColorMapper.GetStatusColor(cellModel.Status);
    }

    private void OnCellFormatting(object? sender, DataGridViewCellFormattingEventArgs e)
    {
        if (e.RowIndex < 0 || e.RowIndex >= CurrentMatrix.Count || e.ColumnIndex < 0 || e.ColumnIndex >= 7 || e.CellStyle == null)
        {
            return;
        }

        var cellModel = CurrentMatrix[e.RowIndex][e.ColumnIndex];
        if (!cellModel.DayNumber.HasValue)
        {
            e.Value = string.Empty;
            e.CellStyle.BackColor = Color.FromArgb(248, 250, 252);
            e.CellStyle.ForeColor = Color.Transparent;
            return;
        }

        e.Value = cellModel.DayNumber.Value.ToString();
        var bg = CalendarColorMapper.GetStatusColor(cellModel.Status);
        e.CellStyle.BackColor = bg;

        if (cellModel.IsToday)
        {
            e.CellStyle.Font = new Font("Segoe UI", 9.5f, FontStyle.Bold);
            e.CellStyle.ForeColor = Color.FromArgb(30, 58, 138); // Deep blue
        }
        else
        {
            e.CellStyle.Font = new Font("Segoe UI", 9f, FontStyle.Regular);
            e.CellStyle.ForeColor = Color.FromArgb(15, 23, 42);
        }
    }

    private void OnCellClick(object? sender, DataGridViewCellEventArgs e)
    {
        if (e.RowIndex < 0 || e.RowIndex >= CurrentMatrix.Count || e.ColumnIndex < 0 || e.ColumnIndex >= 7)
        {
            return;
        }

        var cellModel = CurrentMatrix[e.RowIndex][e.ColumnIndex];
        if (cellModel.DayNumber.HasValue)
        {
            OnDaySelected?.Invoke(cellModel);
        }
    }

    public void SimulateCellClick(int row, int col)
    {
        if (row < 0 || row >= CurrentMatrix.Count || col < 0 || col >= 7)
        {
            return;
        }

        var cellModel = CurrentMatrix[row][col];
        if (cellModel.DayNumber.HasValue)
        {
            OnDaySelected?.Invoke(cellModel);
        }
    }

    public async Task LoadMonthAsync(int year, int month)
    {
        try
        {
            var data = await _apiClient.GetCalendarMonthAsync(year, month);
            SetMonth(year, month, data);
        }
        catch (Exception)
        {
            SetMonth(year, month, null);
        }
    }

    public async Task NavigatePrevMonthAsync()
    {
        var year = CurrentYear;
        var month = CurrentMonth - 1;
        if (month < 1)
        {
            month = 12;
            year--;
        }

        await LoadMonthAsync(year, month);
        OnMonthChanged?.Invoke(year, month);
    }

    public async Task NavigateNextMonthAsync()
    {
        var year = CurrentYear;
        var month = CurrentMonth + 1;
        if (month > 12)
        {
            month = 1;
            year++;
        }

        await LoadMonthAsync(year, month);
        OnMonthChanged?.Invoke(year, month);
    }

    private static string GetMonthTitle(int year, int month)
    {
        var monthNames = new[]
        {
            "Januari", "Februari", "Maret", "April", "Mei", "Juni",
            "Juli", "Agustus", "September", "Oktober", "November", "Desember"
        };

        if (month >= 1 && month <= 12)
        {
            return $"{monthNames[month - 1]} {year}";
        }
        return $"{month} {year}";
    }
}
