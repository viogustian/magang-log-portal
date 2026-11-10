namespace MagangLog.Desktop.Controls;

/// <summary>
/// Horizontal progress strip displaying the 6 onboarding steps and their completion status.
/// </summary>
public class StepIndicatorPanel : Panel
{
    private static readonly string[] DefaultStepTitles =
    [
        "1. Kredensial AI & Sistem",
        "2. Folder Proyek",
        "3. Kata Kunci",
        "4. Intensitas Git",
        "5. Mode Pengiriman",
        "6. Ringkasan"
    ];

    private readonly Label[] _stepLabels;
    private int _currentStep = 0;
    private readonly HashSet<int> _completedSteps = new();

    public int StepCount => DefaultStepTitles.Length;
    public int CurrentStep => _currentStep;
    public IReadOnlyCollection<int> CompletedSteps => _completedSteps;

    public StepIndicatorPanel()
    {
        DoubleBuffered = true;
        Height = 56;
        Dock = DockStyle.Top;
        BackColor = Color.FromArgb(245, 247, 250);
        Padding = new Padding(12, 10, 12, 10);

        var table = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            ColumnCount = DefaultStepTitles.Length,
            RowCount = 1
        };

        for (int i = 0; i < DefaultStepTitles.Length; i++)
        {
            table.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100f / DefaultStepTitles.Length));
        }

        _stepLabels = new Label[DefaultStepTitles.Length];
        for (int i = 0; i < DefaultStepTitles.Length; i++)
        {
            var lbl = new Label
            {
                Dock = DockStyle.Fill,
                TextAlign = ContentAlignment.MiddleCenter,
                Font = new Font(Font.FontFamily, 8.5f, FontStyle.Regular),
                ForeColor = Color.FromArgb(100, 116, 139),
                Text = $"○ {DefaultStepTitles[i]}"
            };
            _stepLabels[i] = lbl;
            table.Controls.Add(lbl, i, 0);
        }

        Controls.Add(table);
        UpdateVisuals();
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
                lbl.Font = new Font(Font.FontFamily, 8.5f, FontStyle.Bold);
                lbl.ForeColor = Color.FromArgb(37, 99, 235); // Accent blue
                lbl.BackColor = Color.FromArgb(239, 246, 255);
            }
            else if (_completedSteps.Contains(i))
            {
                lbl.Text = $"✓ {title}";
                lbl.Font = new Font(Font.FontFamily, 8.5f, FontStyle.Regular);
                lbl.ForeColor = Color.FromArgb(22, 101, 52); // Forest green
                lbl.BackColor = Color.Transparent;
            }
            else
            {
                lbl.Text = $"○ {title}";
                lbl.Font = new Font(Font.FontFamily, 8.5f, FontStyle.Regular);
                lbl.ForeColor = Color.FromArgb(148, 163, 184); // Slate gray
                lbl.BackColor = Color.Transparent;
            }
        }
    }
}

