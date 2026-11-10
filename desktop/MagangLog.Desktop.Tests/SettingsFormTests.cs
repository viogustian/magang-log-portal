using MagangLog.Desktop.Forms;
using MagangLog.Desktop.Models;
using MagangLog.Desktop.Services;
using Xunit;

namespace MagangLog.Desktop.Tests;

public class SettingsFormTests
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

    private static async Task RunStaAsync(Func<Task> action)
    {
        var tcs = new TaskCompletionSource();
        var thread = new Thread(() =>
        {
            try
            {
                action().GetAwaiter().GetResult();
                tcs.SetResult();
            }
            catch (Exception ex)
            {
                tcs.SetException(ex);
            }
        });
        thread.SetApartmentState(ApartmentState.STA);
        thread.Start();
        await tcs.Task;
    }

    [Fact]
    public void TestSettingsForm_InitializesTabsAndDefaultDimensions()
    {
        RunSta(() =>
        {
            using var form = new SettingsForm();

            Assert.Equal("Pengaturan Konfigurasi — MagangLog Portal", form.Text);
            Assert.True(form.Width >= 800);
            Assert.True(form.Height >= 600);
            Assert.NotNull(form.TabControl);
            Assert.True(form.TabControl.TabPages.Count >= 4);

            // Tab names
            Assert.Equal("WorkProfile & Aplikasi", form.TabControl.TabPages[0].Text);
            Assert.Equal("Folder Proyek", form.TabControl.TabPages[1].Text);
            Assert.Equal("Sumber Data & Privasi", form.TabControl.TabPages[2].Text);
            Assert.Equal("Mode Pengiriman", form.TabControl.TabPages[3].Text);
        });
    }

    [Fact]
    public void TestSettingsForm_PopulateFromConfig_MapsToTab1Through4()
    {
        RunSta(() =>
        {
            var config = new SaveConfigRequest
            {
                Review = new ReviewSettingsDto
                {
                    Mode = "notify"
                },
                Sources = new SourcesSettingsDto
                {
                    Git = new GitSourceSettingsDto
                    {
                        Enabled = true,
                        Repositories = new List<string> { @"C:\Projects\Alpha" }
                    },
                    App = new AppSourceSettingsDto
                    {
                        Enabled = true
                    },
                    Browser = new BrowserSourceSettingsDto
                    {
                        Enabled = true,
                        AllowDomains = new List<string> { "github.com", "learn.microsoft.com" }
                    }
                },
                WorkProfile = new WorkProfile
                {
                    ProfileName = "Fullstack Developer",
                    NaturalDescription = "Mengerjakan frontend React dan backend C# API",
                    Applications = new List<ApplicationConfig>
                    {
                        new()
                        {
                            Name = "Fullstack Tools",
                            ProcessNames = new List<string> { "devenv.exe", "Code.exe" },
                            FileExtensions = new List<string> { ".cs", ".tsx", ".ts" }
                        }
                    },
                    BrowserDomains = new List<string> { "github.com", "learn.microsoft.com" }
                }
            };

            using var form = new SettingsForm();
            form.PopulateFromConfig(config);

            // Tab 1 Assertions
            Assert.Equal("Fullstack Developer", form.ProfileName);
            Assert.Equal("Mengerjakan frontend React dan backend C# API", form.NaturalDescription);
            Assert.Contains("devenv.exe", form.Keywords);
            Assert.Contains("Code.exe", form.Keywords);
            Assert.Contains(".cs", form.GetFileExtensions());
            Assert.Contains(".tsx", form.GetFileExtensions());

            // Tab 3 Assertions
            Assert.True(form.GitEnabled);
            Assert.True(form.AppEnabled);
            Assert.True(form.BrowserEnabled);
            Assert.Equal("jarang", form.GitFrequency);
            Assert.Contains("github.com", form.GetAllowDomains());
            Assert.Contains("learn.microsoft.com", form.GetAllowDomains());

            // Tab 4 Assertions
            Assert.Equal("notify", form.ReviewMode);
            Assert.False(form.IsAutoWarningVisible);
            Assert.True(form.IsGuardrailSatisfied);
        });
    }

    [Fact]
    public void TestSettingsForm_AutoModeGuardrail_RequiresConfirmation()
    {
        RunSta(() =>
        {
            using var form = new SettingsForm();
            form.ProfileName = "Software Engineer";

            // Default mode is review -> guardrail satisfied
            form.ReviewMode = "review";
            Assert.False(form.IsAutoWarningVisible);
            Assert.True(form.IsGuardrailSatisfied);

            // Switch to auto mode without checkbox checked -> warning visible, guardrail false
            form.ReviewMode = "auto";
            Assert.True(form.IsAutoWarningVisible);
            Assert.False(form.AutoConfirmed);
            Assert.False(form.IsGuardrailSatisfied);

            // Validation should fail
            var valid = form.ValidateTabs(out var error);
            Assert.False(valid);
            Assert.Contains("otomatis", error?.ToLowerInvariant());

            // Check confirmation box -> guardrail satisfied
            form.AutoConfirmed = true;
            Assert.True(form.IsGuardrailSatisfied);
            valid = form.ValidateTabs(out error);
            Assert.True(valid);
        });
    }

    [Fact]
    public void TestSettingsForm_DomainAllowlistParsing_CleansAndDeduplicates()
    {
        RunSta(() =>
        {
            using var form = new SettingsForm();

            form.AllowDomainsRawText = "  https://github.com/ \r\n learn.microsoft.com\n\nSTACKOVERFLOW.COM;\r\n  github.com  ";
            var parsed = form.GetAllowDomains();

            Assert.Equal(3, parsed.Count);
            Assert.Contains("github.com", parsed);
            Assert.Contains("learn.microsoft.com", parsed);
            Assert.Contains("stackoverflow.com", parsed);

            // Setting domains sets multiline text cleanly
            form.SetAllowDomains(new[] { "agrinesia.co.id", "gitlab.com" });
            Assert.Contains("agrinesia.co.id", form.AllowDomainsRawText);
            Assert.Contains("gitlab.com", form.AllowDomainsRawText);
        });
    }

    [Fact]
    public void TestSettingsForm_FileExtensionParsing_NormalizesDotPrefix()
    {
        RunSta(() =>
        {
            using var form = new SettingsForm();

            form.FileExtensionsRawText = "cs, .py, fig,  .pbix; ts ";
            var exts = form.GetFileExtensions();

            Assert.Equal(5, exts.Count);
            Assert.Contains(".cs", exts);
            Assert.Contains(".py", exts);
            Assert.Contains(".fig", exts);
            Assert.Contains(".pbix", exts);
            Assert.Contains(".ts", exts);
        });
    }

    [Fact]
    public void TestSettingsForm_ApplyToConfig_UpdatesModelCorrectly()
    {
        RunSta(() =>
        {
            using var form = new SettingsForm();

            form.ProfileName = "Backend Engineer";
            form.NaturalDescription = "Membangun REST API FastAPI dan C#";
            form.AddKeyword("fastapi");
            form.AddKeyword("dotnet");
            form.SetFileExtensions(new[] { ".py", ".cs" });
            form.GitFrequency = "sering";
            form.GitEnabled = true;
            form.AppEnabled = true;
            form.BrowserEnabled = false;
            form.SetAllowDomains(new[] { "github.com", "pypi.org" });
            form.ReviewMode = "review";

            var targetConfig = new SaveConfigRequest();
            form.ApplyToConfig(targetConfig);

            Assert.Equal("review", targetConfig.Review.Mode);
            Assert.True(targetConfig.Sources.Git.Enabled);
            Assert.True(targetConfig.Sources.App.Enabled);
            Assert.False(targetConfig.Sources.Browser.Enabled);
            Assert.Contains("github.com", targetConfig.Sources.Browser.AllowDomains);
            Assert.Contains("pypi.org", targetConfig.Sources.Browser.AllowDomains);

            Assert.NotNull(targetConfig.WorkProfile);
            Assert.Equal("Backend Engineer", targetConfig.WorkProfile.ProfileName);
            Assert.Equal("Membangun REST API FastAPI dan C#", targetConfig.WorkProfile.NaturalDescription);
            Assert.Contains("github.com", targetConfig.WorkProfile.BrowserDomains);
        });
    }

    [Fact]
    public void TestSettingsForm_ValidateTabs_FailsWhenProfileNameIsEmpty()
    {
        RunSta(() =>
        {
            using var form = new SettingsForm();
            form.ProfileName = "   "; // empty

            var valid = form.ValidateTabs(out var error);
            Assert.False(valid);
            Assert.Contains("Tab 1", error);
            Assert.Equal(0, form.TabControl.SelectedIndex);
        });
    }

    [Fact]
    public async Task TestSettingsForm_LoadInitialDataAsync_PopulatesPresetsAndActiveConfig()
    {
        var presetsJson = """
        [
            {
                "profile_name": "Frontend Designer",
                "natural_description": "Membuat wireframe dan UI",
                "applications": [
                    {
                        "name": "Design Suite",
                        "process_names": ["Figma.exe", "Photoshop.exe"],
                        "file_extensions": [".fig", ".psd"]
                    }
                ],
                "browser_domains": ["figma.com", "dribbble.com"]
            }
        ]
        """;

        var configJson = """
        {
            "review": { "mode": "review" },
            "sources": {
                "git": { "enabled": true, "repositories": [] },
                "app": { "enabled": true },
                "browser": { "enabled": false, "allow_domains": ["figma.com"] }
            },
            "work_profile": {
                "profile_name": "Frontend Designer",
                "natural_description": "Membuat wireframe dan UI",
                "applications": [
                    {
                        "name": "Design Suite",
                        "process_names": ["Figma.exe", "Photoshop.exe"],
                        "file_extensions": [".fig", ".psd"]
                    }
                ],
                "browser_domains": ["figma.com"]
            }
        }
        """;

        var handler = new MockHttpMessageHandler(req =>
        {
            if (req.RequestUri!.AbsolutePath.Contains("/presets"))
            {
                return new HttpResponseMessage(System.Net.HttpStatusCode.OK)
                {
                    Content = new StringContent(presetsJson, System.Text.Encoding.UTF8, "application/json")
                };
            }
            if (req.RequestUri.AbsolutePath.Contains("/config"))
            {
                return new HttpResponseMessage(System.Net.HttpStatusCode.OK)
                {
                    Content = new StringContent(configJson, System.Text.Encoding.UTF8, "application/json")
                };
            }
            return new HttpResponseMessage(System.Net.HttpStatusCode.OK)
            {
                Content = new StringContent("{}", System.Text.Encoding.UTF8, "application/json")
            };
        });

        var client = new BackendApiClient(new HttpClient(handler));

        await RunStaAsync(async () =>
        {
            using var form = new SettingsForm(client);
            await form.LoadInitialDataAsync();

            Assert.True(form.PresetsComboBox.Items.Count >= 2);
            Assert.Equal("Frontend Designer", form.ProfileName);
            Assert.Contains("Figma.exe", form.Keywords);
            Assert.Contains(".fig", form.GetFileExtensions());
        });
    }

    [Fact]
    public async Task TestSettingsForm_PredictProfileAiAsync_UpdatesKeywordsFromBackend()
    {
        var predictJson = """
        {
            "source": "gemini",
            "profile": {
                "profile_name": "Data Analyst",
                "natural_description": "Analisis query SQL dan visualisasi PowerBI",
                "applications": [
                    {
                        "name": "BI Tools",
                        "process_names": ["PBIDesktop.exe", "dbeaver.exe"],
                        "file_extensions": [".pbix", ".sql"]
                    }
                ],
                "browser_domains": ["tableau.com"]
            }
        }
        """;

        var handler = new MockHttpMessageHandler(predictJson);
        var client = new BackendApiClient(new HttpClient(handler));

        await RunStaAsync(async () =>
        {
            using var form = new SettingsForm(client);
            form.NaturalDescription = "Analisis query SQL dan visualisasi PowerBI";

            await form.PredictProfileAiAsync();

            Assert.Equal("Data Analyst", form.ProfileName);
            Assert.Contains("PBIDesktop.exe", form.Keywords);
            Assert.Contains("dbeaver.exe", form.Keywords);
            Assert.Contains(".pbix", form.GetFileExtensions());
            Assert.Contains(".sql", form.GetFileExtensions());
            Assert.True(form.IsAiBannerVisible);
            Assert.Contains("Berhasil", form.AiBannerLabel.Text);
        });
    }
}
