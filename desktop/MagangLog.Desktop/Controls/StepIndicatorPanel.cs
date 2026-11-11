namespace MagangLog.Desktop.Controls;

/// <summary>
/// Horizontal progress strip displaying the 6 onboarding steps and their completion status.
/// Renders single-line items with proportional column widths so step labels remain vertically aligned
/// and never wrap awkwardly or clip across Windows DPI / text scaling levels.
/// </summary>
public class StepIndicatorPanel : Panel
{
    private static readonly string[] DefaultStepTitles =
    [
        "1. Sistem & AI",
        "2. Folder Proyek",
        "3. Kata Kunci",
        "4. Intensitas Git",
        "5. Mode Kirim",
        "6. Ringkasan"
    ];

    private const TextFormatFlags SingleLineFlags =
        TextFormatFlags.SingleLine |
        TextFormatFlags.HorizontalCenter |
        TextFormatFlags.VerticalCenter |
        TextFormatFlags.EndEllipsis |
        TextFormatFlags.NoPrefix;

    private sealed class SingleLineStepLabel : Label
    {
        protected override void OnPaint(PaintEventArgs e)
        {
            var bgColor = BackColor == Color.Transparent && Parent != null ? Parent.BackColor : BackColor;
            using var bgBrush = new SolidBrush(bgColor);
            e.Graphics.FillRectangle(bgBrush, ClientRectangle);

            TextRenderer.DrawText(e.Graphics, Text, Font, ClientRectangle, ForeColor, SingleLineFlags);
        }
    }

    private readonly TableLayoutPanel _table;
    private readonly Label[] _stepLabels;
    private readonly Font _regularFont;
    private readonly Font _boldFont;
    private readonly int[] _columnWidths;
    private readonly int _requiredMinWidth;
    private int _currentStep = 0;
    private readonly HashSet<int> _completedSteps = new();

    public int StepCount => DefaultStepTitles.Length;
    public int CurrentStep => _currentStep;
    public IReadOnlyCollection<int> CompletedSteps => _completedSteps;

    public StepIndicatorPanel()
    {
        DoubleBuffered = true;
        Dock = DockStyle.Top;
        BackColor = Color.FromArgb(245, 247, 250);
        Padding = new Padding(12, 8, 12, 9);

        _regularFont = new Font("Segoe UI", 8.5f, FontStyle.Regular);
        _boldFont = new Font("Segoe UI", 8.5f, FontStyle.Bold);

        var maxTextHeight = 0;
        _columnWidths = new int[DefaultStepTitles.Length];
        for (int i = 0; i < DefaultStepTitles.Length; i++)
        {
            var measured = TextRenderer.MeasureText(
                $"● {DefaultStepTitles[i]}",
                _boldFont,
                new Size(int.MaxValue, int.MaxValue),
                TextFormatFlags.SingleLine | TextFormatFlags.NoPrefix);
            _columnWidths[i] = measured.Width + 16;
            maxTextHeight = Math.Max(maxTextHeight, measured.Height);
        }

        Height = Math.Max(52, maxTextHeight + 28);
        var cellHorizontalMarginSum = DefaultStepTitles.Length * 4;
        _requiredMinWidth = _columnWidths.Sum() + Padding.Horizontal + cellHorizontalMarginSum;

        _table = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            ColumnCount = DefaultStepTitles.Length,
            RowCount = 1,
            Margin = Padding.Empty,
            Padding = Padding.Empty,
            BackColor = BackColor
        };
        _table.RowStyles.Add(new RowStyle(SizeType.Percent, 100f));

        float totalColumnWeight = _columnWidths.Sum();
        for (int i = 0; i < DefaultStepTitles.Length; i++)
        {
            var pct = _columnWidths[i] / totalColumnWeight * 100f;
            _table.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, pct));
        }

        _stepLabels = new Label[DefaultStepTitles.Length];
        for (int i = 0; i < DefaultStepTitles.Length; i++)
        {
            var lbl = new SingleLineStepLabel
            {
                AutoSize = false,
                Dock = DockStyle.Fill,
                Margin = new Padding(2, 0, 2, 0),
                Padding = new Padding(4, 0, 4, 0),
                TextAlign = ContentAlignment.MiddleCenter,
                UseMnemonic = false,
                Font = _regularFont,
                ForeColor = Color.FromArgb(100, 116, 139),
                BackColor = Color.Transparent,
                Text = $"○ {DefaultStepTitles[i]}"
            };
            _stepLabels[i] = lbl;
            _table.Controls.Add(lbl, i, 0);
        }

        Controls.Add(_table);
        UpdateVisuals();
    }

    /// <summary>
    /// Returns the minimum control width needed so all 6 step titles fit without truncation or wrapping.
    /// </summary>
    public int GetRequiredMinimumWidth() => _requiredMinWidth;

    protected override void OnPaint(PaintEventArgs e)
    {
        base.OnPaint(e);
        using var pen = new Pen(Color.FromArgb(226, 232, 240));
        e.Graphics.DrawLine(pen, 0, Height - 1, Width, Height - 1);
    }

    protected override void Dispose(bool disposing)
    {
        if (disposing)
        {
            _regularFont.Dispose();
            _boldFont.Dispose();
        }
        base.Dispose(disposing);
    }

    /// <summary>
    /// Update active step and completed steps.
    /// </summary>
    public void UpdateStep(int currentStep, IReadOnlyList<int>? completedSteps = null)
    {
        _currentStep = Math.Clamp(currentStep, 0, StepCount - 1);
        _completedSteps.Clear();
        if (completedSteps != null)
        {
            foreach (var s in completedSteps)
            {
                _completedSteps.Add(s);
            }
        }
        UpdateVisuals();
    }

    private void UpdateVisuals()
    {
        for (int i = 0; i < _stepLabels.Length; i++)
        {
            var title = DefaultStepTitles[i];
            var lbl = _stepLabels[i];

            if (i == _currentStep)
            {
                lbl.Text = $"● {title}";
                lbl.Font = _boldFont;
                lbl.ForeColor = Color.FromArgb(37, 99, 235); // Accent blue
                lbl.BackColor = Color.FromArgb(239, 246, 255);
            }
            else if (_completedSteps.Contains(i))
            {
                lbl.Text = $"✓ {title}";
                lbl.Font = _regularFont;
                lbl.ForeColor = Color.FromArgb(22, 101, 52); // Forest green
                lbl.BackColor = Color.Transparent;
            }
            else
            {
                lbl.Text = $"○ {title}";
                lbl.Font = _regularFont;
                lbl.ForeColor = Color.FromArgb(148, 163, 184); // Slate gray
                lbl.BackColor = Color.Transparent;
            }
        }
    }
}
