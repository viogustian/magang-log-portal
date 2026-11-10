using System.Drawing;
using System.Text.Json;
using MagangLog.Desktop.Models;
using Xunit;

namespace MagangLog.Desktop.Tests;

public class EvidenceItemTests
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true
    };

    [Fact]
    public void TestParseEvidenceFeedResponseFromJson()
    {
        var json = """
        {
            "items": [
                {
                    "id": "ev-1",
                    "source": "git",
                    "kind": "commit",
                    "ts": "2026-11-10T09:15:00Z",
                    "title": "feat: add login screen",
                    "detail": "Commit details here",
                    "strength": "strong"
                },
                {
                    "id": "ev-2",
                    "source": "app",
                    "kind": "window",
                    "ts": "2026-11-10T10:30:00Z",
                    "title": "Figma - Dashboard UI",
                    "detail": "Figma.exe",
                    "strength": "weak"
                }
            ]
        }
        """;

        var response = JsonSerializer.Deserialize<EvidenceFeedResponse>(json, JsonOptions);

        Assert.NotNull(response);
        Assert.NotNull(response.Items);
        Assert.Equal(2, response.Items.Count);

        var first = response.Items[0];
        Assert.Equal("ev-1", first.Id);
        Assert.Equal("git", first.Source);
        Assert.Equal("commit", first.Kind);
        Assert.Equal("2026-11-10T09:15:00Z", first.Timestamp);
        Assert.Equal("feat: add login screen", first.Title);
        Assert.Equal("Commit details here", first.Detail);
        Assert.Equal("strong", first.Strength);
    }

    [Theory]
    [InlineData("git", "📦 Git")]
    [InlineData("GIT", "📦 Git")]
    [InlineData("app", "💻 App")]
    [InlineData("browser", "🌐 Browser")]
    [InlineData("notes", "📝 Notes")]
    [InlineData("note", "📝 Notes")]
    [InlineData("other", "📌 Other")]
    public void TestGetSourceBadge(string source, string expectedBadge)
    {
        var badge = EvidenceHelper.GetSourceBadge(source);
        Assert.Equal(expectedBadge, badge);
    }

    [Fact]
    public void TestFormatTimeFromIsoString()
    {
        var iso = "2026-11-10T14:45:00Z";
        var formatted = EvidenceHelper.FormatTime(iso);
        Assert.Matches(@"^\d{2}:\d{2}$", formatted);
    }

    [Fact]
    public void TestFilterEvidenceItems()
    {
        var items = new List<EvidenceItem>
        {
            new() { Id = "1", Source = "git", Title = "Git 1" },
            new() { Id = "2", Source = "app", Title = "App 1" },
            new() { Id = "3", Source = "browser", Title = "Web 1" },
            new() { Id = "4", Source = "notes", Title = "Note 1" },
            new() { Id = "5", Source = "note", Title = "Note 2" }
        };

        Assert.Equal(5, EvidenceHelper.FilterItems(items, "Semua").Count);
        Assert.Single(EvidenceHelper.FilterItems(items, "Git"));
        Assert.Single(EvidenceHelper.FilterItems(items, "App"));
        Assert.Single(EvidenceHelper.FilterItems(items, "Browser"));
        Assert.Equal(2, EvidenceHelper.FilterItems(items, "Notes").Count);
    }

    [Fact]
    public void TestStrengthColorMapping()
    {
        var strongColor = EvidenceHelper.GetStrengthColor("strong");
        var weakColor = EvidenceHelper.GetStrengthColor("weak");

        Assert.Equal(Color.FromArgb(200, 230, 200), strongColor);
        Assert.Equal(Color.FromArgb(255, 245, 200), weakColor);
    }
}
