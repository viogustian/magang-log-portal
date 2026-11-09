using MagangLog.Desktop.Forms;

namespace MagangLog.Desktop;

internal static class Program
{
    /// <summary>
    /// The main entry point for the application.
    /// </summary>
    [STAThread]
    private static void Main()
    {
        ApplicationConfiguration.Initialize();
        Application.Run(new MainDashboardForm());
    }
}
