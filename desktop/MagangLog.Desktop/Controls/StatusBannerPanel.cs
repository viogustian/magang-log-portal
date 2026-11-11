using System.Drawing;
using System.Globalization;
using MagangLog.Desktop.Models;

namespace MagangLog.Desktop.Controls;

/// <summary>
/// Status Hero Banner panel docked at the top of MainDashboardForm.
/// Prominently displays Indonesian current date, dynamic status badge,
/// and quick-action buttons for manual pipeline execution and Monev portal navigation.
/// </summary>
public class StatusBannerPanel : Panel
{
    private static readonly CultureInfo IdCulture = new("id-ID");

    public Label DateLabel { get; }
    public Label StatusBadgeLabel { get; }
    public Button RunPipelineButton { get; }
    public Button OpenPortalButton { get; }

    public DashboardStatus CurrentStatus { get; private set; } = DashboardStatus.PerluInput;
    public bool IsOffline { get; private set; } = false;

    public StatusBannerPanel()
    {
        Dock = DockStyle.Top;
        Height = 80;
        Padding = new Padding(24, 14, 24, 14);
        BackColor = Color.FromArgb(255, 245, 200); // Default to initial yellow state

        // Left Container for Date and Status Badge
        var leftFlow = new FlowLayoutPanel
        {
            Dock = DockStyle.Left,
            FlowDirection = FlowDirection.LeftToRight,
            AutoSize = true,
            BackColor = Color.Transparent,
            WrapContents = false
        };

        var infoPanel = new FlowLayoutPanel
        {
            AutoSize = true,
            FlowDirection = FlowDirection.TopDown,
            WrapContents = false,
            Dock = DockStyle.Left,
            Margin = Padding.Empty,
            Padding = Padding.Empty,
            BackColor = Color.Transparent
        };

        var lblTodayTitle = new Label
        {
            Text = "Status Hari Ini:",
            Font = new Font(Font.FontFamily, 9.5f, FontStyle.Regular),
            ForeColor = Color.FromArgb(71, 85, 105),
            AutoSize = true,
            Margin = new Padding(0, 2, 0, 2)
        };

        DateLabel = new Label
        {
            Text = DateTime.Now.ToString("dddd, dd MMMM yyyy", IdCulture),
            Font = new Font(Font.FontFamily, 11f, FontStyle.Bold),
            ForeColor = Color.FromArgb(15, 23, 42),
            AutoSize = true,
            Margin = Padding.Empty
        };

        StatusBadgeLabel = new Label
        {
            Text = "🟡 MEMERIKSA...",
            Font = new Font(Font.FontFamily, 10.5f, FontStyle.Bold),
            ForeColor = Color.FromArgb(15, 23, 42),
            BackColor = Color.FromArgb(255, 245, 200),
            AutoSize = true,
            Padding = new Padding(12, 6, 12, 6),
            Margin = new Padding(20, 10, 0, 0),
            TextAlign = ContentAlignment.MiddleCenter
        };

        infoPanel.Controls.Add(lblTodayTitle);
        infoPanel.Controls.Add(DateLabel);

        leftFlow.Controls.Add(infoPanel);
        leftFlow.Controls.Add(StatusBadgeLabel);

        // Right Flow for Action Buttons
        var rightFlow = new FlowLayoutPanel
        {
            Dock = DockStyle.Right,
            FlowDirection = FlowDirection.RightToLeft,
            AutoSize = true,
            BackColor = Color.Transparent,
            WrapContents = false,
            Padding = new Padding(0, 8, 0, 0)
        };

        OpenPortalButton = new Button
        {
            Text = "Buka Portal Monev",
            Height = 36,
            AutoSize = true,
            Padding = new Padding(14, 0, 14, 0),
            BackColor = Color.White,
            ForeColor = Color.FromArgb(30, 41, 59),
            FlatStyle = FlatStyle.Flat,
            Cursor = Cursors.Hand,
            Margin = new Padding(8, 0, 0, 0),
            Font = new Font(Font.FontFamily, 9.5f, FontStyle.Regular)
        };
        OpenPortalButton.FlatAppearance.BorderColor = Color.FromArgb(203, 213, 225);

        RunPipelineButton = new Button
        {
            Text = "Jalankan Pipeline Sekarang",
            Height = 36,
            AutoSize = true,
            Padding = new Padding(14, 0, 14, 0),
            BackColor = Color.FromArgb(14, 165, 233),
            ForeColor = Color.White,
            FlatStyle = FlatStyle.Flat,
            Cursor = Cursors.Hand,
            Margin = new Padding(8, 0, 0, 0),
            Font = new Font(Font.FontFamily, 9.5f, FontStyle.Bold)
        };
        RunPipelineButton.FlatAppearance.BorderSize = 0;

        rightFlow.Controls.Add(OpenPortalButton);
        rightFlow.Controls.Add(RunPipelineButton);

        Controls.Add(leftFlow);
        Controls.Add(rightFlow);
    }

    /// <summary>
    /// Update status banner display based on TodayStatusResponse from backend.
    /// </summary>
    public void UpdateStatus(TodayStatusResponse? response)
    {
        if (response == null)
        {
            UpdateOffline();
            return;
        }

        IsOffline = false;
        CurrentStatus = DashboardStatusHelper.MapStatus(
            response.Status,
            hasSubmitted: response.HasSubmittedEntry,
            isHoliday: response.IsHoliday
        );

        var color = DashboardStatusHelper.GetBadgeColor(CurrentStatus);
        var text = DashboardStatusHelper.GetBadgeText(CurrentStatus, response.HolidayName);

        BackColor = color;
        StatusBadgeLabel.Text = text;
        StatusBadgeLabel.BackColor = color;

        RunPipelineButton.Enabled = true;
        OpenPortalButton.Enabled = true;
    }

    /// <summary>
    /// Update status banner to offline state when backend communication fails.
    /// Disables action buttons safely without throwing or crashing.
    /// </summary>
    public void UpdateOffline()
    {
        IsOffline = true;
        CurrentStatus = DashboardStatus.Offline;

        var color = DashboardStatusHelper.GetBadgeColor(DashboardStatus.Offline);
        var text = DashboardStatusHelper.GetBadgeText(DashboardStatus.Offline);

        BackColor = color;
        StatusBadgeLabel.Text = text;
        StatusBadgeLabel.BackColor = color;

        RunPipelineButton.Enabled = false;
        // Monev portal can still be opened even if local backend is down
        OpenPortalButton.Enabled = true;
    }

    /// <summary>
    /// Set visual feedback on the RunPipeline button while execution is in progress.
    /// </summary>
    public void SetPipelineRunning(bool isRunning)
    {
        if (isRunning)
        {
            RunPipelineButton.Enabled = false;
            RunPipelineButton.Text = "⏳ Menjalankan Pipeline...";
            RunPipelineButton.BackColor = Color.FromArgb(100, 116, 139);
        }
        else
        {
            RunPipelineButton.Enabled = !IsOffline;
            RunPipelineButton.Text = "Jalankan Pipeline Sekarang";
            RunPipelineButton.BackColor = Color.FromArgb(14, 165, 233);
        }
    }
}
