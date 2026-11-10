using System.Drawing;
using MagangLog.Desktop.Controls;
using MagangLog.Desktop.Models;
using Xunit;

namespace MagangLog.Desktop.Tests;

public class EvidencePanelTests
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
    public void TestEvidencePanelInitializesWithGridAndFilterDropdown()
    {
        RunSta(() =>
        {
            using var panel = new EvidencePanel();

            Assert.NotNull(panel.FilterSourceComboBox);
            Assert.Equal(5, panel.FilterSourceComboBox.Items.Count);
            Assert.Contains("Semua", panel.FilterSourceComboBox.Items.Cast<string>());
            Assert.Contains("Git", panel.FilterSourceComboBox.Items.Cast<string>());
            Assert.Contains("App", panel.FilterSourceComboBox.Items.Cast<string>());
            Assert.Contains("Browser", panel.FilterSourceComboBox.Items.Cast<string>());
            Assert.Contains("Notes", panel.FilterSourceComboBox.Items.Cast<string>());
            Assert.Equal("Semua", panel.FilterSourceComboBox.SelectedItem);

            Assert.NotNull(panel.EvidenceGrid);
            Assert.True(panel.EvidenceGrid.ReadOnly);
            Assert.False(panel.EvidenceGrid.AllowUserToAddRows);
            Assert.Equal(DataGridViewSelectionMode.FullRowSelect, panel.EvidenceGrid.SelectionMode);

            Assert.Equal(4, panel.EvidenceGrid.Columns.Count);
            Assert.Equal("Waktu", panel.EvidenceGrid.Columns[0].HeaderText);
            Assert.Equal("Sumber", panel.EvidenceGrid.Columns[1].HeaderText);
            Assert.Equal("Judul", panel.EvidenceGrid.Columns[2].HeaderText);
            Assert.Equal("Kekuatan", panel.EvidenceGrid.Columns[3].HeaderText);

            Assert.NotNull(panel.EmptyPlaceholderLabel);
            Assert.True(panel.EmptyPlaceholderLabel.Visible);
            Assert.Equal("Belum ada aktivitas terekam hari ini", panel.EmptyPlaceholderLabel.Text);
        });
    }

    [Fact]
    public void TestSetEvidenceItemsPopulatesGridRows()
    {
        RunSta(() =>
        {
            using var panel = new EvidencePanel();
            var items = new List<EvidenceItem>
            {
                new()
                {
                    Id = "1",
                    Source = "git",
                    Kind = "commit",
                    Timestamp = "2026-11-10T09:15:00Z",
                    Title = "feat: add login screen",
                    Detail = "Commit hash 123",
                    Strength = "strong"
                },
                new()
                {
                    Id = "2",
                    Source = "app",
                    Kind = "window",
                    Timestamp = "2026-11-10T10:30:00Z",
                    Title = "Figma - Wireframe",
                    Detail = "Figma.exe",
                    Strength = "weak"
                }
            };

            panel.SetEvidenceItems(items);

            Assert.False(panel.EmptyPlaceholderLabel.Visible);
            Assert.Equal(2, panel.EvidenceGrid.Rows.Count);

            var row0 = panel.EvidenceGrid.Rows[0];
            Assert.Matches(@"^\d{2}:\d{2}$", row0.Cells[0].Value?.ToString() ?? "");
            Assert.Equal("📦 Git", row0.Cells[1].Value);
            Assert.Equal("feat: add login screen", row0.Cells[2].Value);
            Assert.Equal("strong", row0.Cells[3].Value);
        });
    }

    [Fact]
    public void TestFilterSourceComboBoxFiltersGridInstantly()
    {
        RunSta(() =>
        {
            using var panel = new EvidencePanel();
            var items = new List<EvidenceItem>
            {
                new() { Id = "1", Source = "git", Title = "Git Commit 1", Strength = "strong" },
                new() { Id = "2", Source = "app", Title = "Figma Design", Strength = "weak" },
                new() { Id = "3", Source = "browser", Title = "Docs MDN", Strength = "weak" },
                new() { Id = "4", Source = "notes", Title = "Standup note", Strength = "strong" }
            };

            panel.SetEvidenceItems(items);
            Assert.Equal(4, panel.EvidenceGrid.Rows.Count);

            // Filter to Git
            panel.FilterSourceComboBox.SelectedItem = "Git";
            Assert.Single(panel.EvidenceGrid.Rows);
            Assert.Equal("Git Commit 1", panel.EvidenceGrid.Rows[0].Cells[2].Value);

            // Filter to App
            panel.FilterSourceComboBox.SelectedItem = "App";
            Assert.Single(panel.EvidenceGrid.Rows);
            Assert.Equal("Figma Design", panel.EvidenceGrid.Rows[0].Cells[2].Value);

            // Filter to Notes
            panel.FilterSourceComboBox.SelectedItem = "Notes";
            Assert.Single(panel.EvidenceGrid.Rows);
            Assert.Equal("Standup note", panel.EvidenceGrid.Rows[0].Cells[2].Value);

            // Filter back to Semua
            panel.FilterSourceComboBox.SelectedItem = "Semua";
            Assert.Equal(4, panel.EvidenceGrid.Rows.Count);
        });
    }

    [Fact]
    public void TestEmptyPlaceholderShowsWhenNoItemsMatchFilter()
    {
        RunSta(() =>
        {
            using var panel = new EvidencePanel();
            var items = new List<EvidenceItem>
            {
                new() { Id = "1", Source = "git", Title = "Git Commit 1" }
            };

            panel.SetEvidenceItems(items);
            Assert.False(panel.EmptyPlaceholderLabel.Visible);

            panel.FilterSourceComboBox.SelectedItem = "Browser";
            Assert.Equal(0, panel.EvidenceGrid.Rows.Count);
            Assert.True(panel.EmptyPlaceholderLabel.Visible);
        });
    }

    [Fact]
    public void TestCellFormattingAppliesColorsForStrength()
    {
        RunSta(() =>
        {
            using var panel = new EvidencePanel();
            var items = new List<EvidenceItem>
            {
                new() { Id = "1", Source = "git", Title = "Git Commit 1", Strength = "strong" },
                new() { Id = "2", Source = "app", Title = "Figma Design", Strength = "weak" }
            };

            panel.SetEvidenceItems(items);

            var cellStyle0 = new DataGridViewCellStyle();
            panel.TriggerCellFormatting(row: 0, col: 3, value: "strong", cellStyle: cellStyle0);
            Assert.Equal(Color.FromArgb(200, 230, 200), cellStyle0.BackColor);

            var cellStyle1 = new DataGridViewCellStyle();
            panel.TriggerCellFormatting(row: 1, col: 3, value: "weak", cellStyle: cellStyle1);
            Assert.Equal(Color.FromArgb(255, 245, 200), cellStyle1.BackColor);
        });
    }
}
