using MagangLog.Desktop.Forms;
using MagangLog.Desktop.Services;
using Xunit;

namespace MagangLog.Desktop.Tests;

public class MainDashboardFormTests
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
    public void TestIsOnboardingRequiredWhenConfigMissing()
    {
        RunSta(() =>
        {
            var handler = new MockHttpMessageHandler("{}");
            var client = new BackendApiClient(new HttpClient(handler));

            using var form = new MainDashboardForm(client)
            {
                ConfigFilePath = "non_existent_config_file_path.yaml",
                OnboardingComplete = false
            };

            Assert.True(form.IsOnboardingRequired());
        });
    }

    [Fact]
    public void TestIsOnboardingRequiredWhenConfigExists()
    {
        RunSta(() =>
        {
            var tempConfig = Path.GetTempFileName();
            try
            {
                File.WriteAllText(tempConfig, "timezone: Asia/Jakarta");

                var handler = new MockHttpMessageHandler("{}");
                var client = new BackendApiClient(new HttpClient(handler));

                using var form = new MainDashboardForm(client)
                {
                    ConfigFilePath = tempConfig,
                    OnboardingComplete = false
                };

                Assert.False(form.IsOnboardingRequired());
            }
            finally
            {
                if (File.Exists(tempConfig))
                {
                    File.Delete(tempConfig);
                }
            }
        });
    }

    [Fact]
    public void TestIsOnboardingRequiredWhenOnboardingAlreadyComplete()
    {
        RunSta(() =>
        {
            var handler = new MockHttpMessageHandler("{}");
            var client = new BackendApiClient(new HttpClient(handler));

            using var form = new MainDashboardForm(client)
            {
                ConfigFilePath = "non_existent_config_file_path.yaml",
                OnboardingComplete = true
            };

            Assert.False(form.IsOnboardingRequired());
        });
    }
}

