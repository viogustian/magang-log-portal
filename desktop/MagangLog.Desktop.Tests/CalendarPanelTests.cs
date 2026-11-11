using System.Drawing;
using MagangLog.Desktop.Controls;
using MagangLog.Desktop.Models;
using MagangLog.Desktop.Services;
using Xunit;

namespace MagangLog.Desktop.Tests;

public class CalendarPanelTests
{
    private static void RunSta(Action action)
    {
        Exception? ex = null;
        var thread = new Thread(() =>
        {
            try
            {
                action();
            }
            catch (Exception e)
            {
                ex = e;
            }
        });
        thread.SetApartmentState(ApartmentState.STA);
        thread.Start();
        thread.Join();

        if (ex != null)
        {
            System.Runtime.ExceptionServices.ExceptionDispatchInfo.Capture(ex).Throw();
        }
    }

    [Fact]
    public void TestCalendarPanelInitializesWithSevenColumns()
    {
        RunSta(() =>
        {
            using var panel = new CalendarPanel();

            Assert.Equal(7, panel.CalendarGrid.ColumnCount);
            Assert.Equal("Sen", panel.CalendarGrid.Columns[0].HeaderText);
            Assert.Equal("Sel", panel.CalendarGrid.Columns[1].HeaderText);
            Assert.Equal("Rab", panel.CalendarGrid.Columns[2].HeaderText);
            Assert.Equal("Kam", panel.CalendarGrid.Columns[3].HeaderText);
            Assert.Equal("Jum", panel.CalendarGrid.Columns[4].HeaderText);
            Assert.Equal("Sab", panel.CalendarGrid.Columns[5].HeaderText);
            Assert.Equal("Min", panel.CalendarGrid.Columns[6].HeaderText);

            Assert.NotNull(panel.PrevMonthButton);
            Assert.NotNull(panel.NextMonthButton);
            Assert.NotNull(panel.MonthTitleLabel);
        });
    }

    [Fact]
    public void TestSetMonthUpdatesGridRowCountAndTitle()
    {
        RunSta(() =>
        {
            using var panel = new CalendarPanel();
            panel.SetMonth(2026, 10);

            Assert.Contains("Oktober 2026", panel.MonthTitleLabel.Text);
            Assert.Equal(5, panel.CalendarGrid.RowCount);
            Assert.Equal(5, panel.CurrentMatrix.Count);
        });
    }

    [Fact]
    public async Task TestPrevAndNextMonthNavigation()
    {
        var handler = new MockHttpMessageHandler("{\"days\":[]}");
        var client = new BackendApiClient(new HttpClient(handler));

        CalendarPanel? panel = null;
        RunSta(() =>
        {
            panel = new CalendarPanel(client);
            panel.SetMonth(2026, 10);
        });

        try
        {
            int? changedYear = null;
            int? changedMonth = null;
            panel!.OnMonthChanged += (y, m) =>
            {
                changedYear = y;
                changedMonth = m;
            };

            await panel.NavigatePrevMonthAsync();
            Assert.Equal(2026, panel.CurrentYear);
            Assert.Equal(9, panel.CurrentMonth);
            Assert.Equal(2026, changedYear);
            Assert.Equal(9, changedMonth);

            await panel.NavigateNextMonthAsync();
            Assert.Equal(2026, panel.CurrentYear);
            Assert.Equal(10, panel.CurrentMonth);
        }
        finally
        {
            panel?.Dispose();
        }
    }

    [Fact]
    public void TestCellClick_FiresOnDaySelected_ForValidDay()
    {
        RunSta(() =>
        {
            using var panel = new CalendarPanel();
            panel.SetMonth(2026, 10);

            CalendarDayCellModel? selected = null;
            panel.OnDaySelected += cell => selected = cell;

            // Row 0, Col 3 is October 1st
            panel.SimulateCellClick(0, 3);

            Assert.NotNull(selected);
            Assert.Equal(1, selected.DayNumber);
            Assert.Equal("2026-10-01", selected.DateString);

            // Row 0, Col 0 is padding (no day)
            selected = null;
            panel.SimulateCellClick(0, 0);
            Assert.Null(selected);
        });
    }

    [Fact]
    public void TestCellFormatting_AppliesStatusBackgroundColor()
    {
        RunSta(() =>
        {
            var data = new MonthCalendarResponse
            {
                Days = new List<CalendarDayInfo>
                {
                    new() { Date = "2026-10-01", DayName = "Kamis", Status = "TERKIRIM" }
                }
            };

            using var panel = new CalendarPanel();
            panel.SetMonth(2026, 10, data);

            var color = panel.GetCellBackgroundColor(0, 3);
            Assert.Equal(Color.LightGreen.ToArgb(), color.ToArgb());
        });
    }

    [Fact]
    public void TestCalendarLayout_HeaderDoesNotOverlapGridAndSixWeekMonthFitsCleanly()
    {
        RunSta(() =>
        {
            using var dashboard = new MagangLog.Desktop.Forms.MainDashboardForm();
            dashboard.Width = dashboard.MinimumSize.Width; // 800px narrowest supported width
            dashboard.CreateControl();
            dashboard.PerformLayout();

            var panel = dashboard.CalendarPanel;
            panel.SetMonth(2026, 11); // November 2026 spans 6 calendar rows
            panel.PerformLayout();

            var headerPanel = panel.Controls.OfType<Panel>().Single(c => c.Dock == DockStyle.Top);
            Assert.True(
                panel.CalendarGrid.Top >= headerPanel.Bottom,
                $"CalendarGrid.Top ({panel.CalendarGrid.Top}) overlaps headerPanel.Bottom ({headerPanel.Bottom}).");

            var flows = headerPanel.Controls.OfType<FlowLayoutPanel>().ToList();
            var navFlow = flows.Single(f => f.Dock == DockStyle.Left);
            var legendFlow = flows.Single(f => f.Dock == DockStyle.Right);
            Assert.True(
                legendFlow.Left >= navFlow.Right,
                $"legendFlow.Left ({legendFlow.Left}) collides with navFlow.Right ({navFlow.Right}) at minimum width.");

            Assert.Equal(6, panel.CalendarGrid.RowCount);
            int totalRowsHeight = panel.CalendarGrid.Rows.Cast<DataGridViewRow>().Sum(r => r.Height);
            int neededHeight = panel.CalendarGrid.ColumnHeadersHeight + totalRowsHeight;
            Assert.True(
                neededHeight <= panel.CalendarGrid.ClientSize.Height + 2,
                $"6-row month needs {neededHeight}px inside CalendarGrid, exceeds ClientSize.Height ({panel.CalendarGrid.ClientSize.Height}px).");
        });
    }
}
