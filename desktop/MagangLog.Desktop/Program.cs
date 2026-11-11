using System.Diagnostics;
using System.IO;
using System.Net.Http;
using System.Threading;
using MagangLog.Desktop.Forms;

namespace MagangLog.Desktop;

internal static class Program
{
    private const string HealthEndpoint = "http://127.0.0.1:8765/api/health";
    private static Process? _backendProcess;

    /// <summary>
    /// The main entry point for the application.
    /// </summary>
    [STAThread]
    private static void Main()
    {
        ApplicationConfiguration.Initialize();
        TryStartBackendServer();
        try
        {
            Application.Run(new MainDashboardForm());
        }
        finally
        {
            TryStopBackendServer();
        }
    }

    private static bool IsBackendHealthy()
    {
        try
        {
            using var client = new HttpClient { Timeout = TimeSpan.FromMilliseconds(400) };
            var res = client.GetAsync(HealthEndpoint).GetAwaiter().GetResult();
            return res.IsSuccessStatusCode;
        }
        catch
        {
            return false;
        }
    }

    private static string ResolveWorkDirectory(string baseDir)
    {
        if (File.Exists(Path.Combine(baseDir, "pyproject.toml")))
        {
            return baseDir;
        }

        var parent = Directory.GetParent(baseDir)?.FullName;
        if (parent != null && File.Exists(Path.Combine(parent, "pyproject.toml")))
        {
            return parent;
        }

        var rootDir = Directory.GetParent(parent ?? "")?.FullName;
        if (rootDir != null && File.Exists(Path.Combine(rootDir, "pyproject.toml")))
        {
            return rootDir;
        }

        return baseDir;
    }

    private static (string FileName, string Arguments)? ResolveBackendCommand(string baseDir, string workDir)
    {
        var bundledCandidates = new[]
        {
            Path.Combine(baseDir, "backend", "magang-log.exe"),
            Path.Combine(baseDir, "magang-log.exe")
        };

        foreach (var candidate in bundledCandidates)
        {
            if (File.Exists(candidate))
            {
                return (candidate, "ui --host 127.0.0.1 --port 8765 --server-only");
            }
        }

        var pythonCandidates = new[]
        {
            Path.Combine(workDir, ".venv", "Scripts", "python.exe"),
            Path.Combine(baseDir, ".venv", "Scripts", "python.exe"),
            Path.Combine(baseDir, "..", ".venv", "Scripts", "python.exe"),
            Path.Combine(baseDir, "..", "..", ".venv", "Scripts", "python.exe"),
            Path.Combine(baseDir, "venv", "Scripts", "python.exe"),
            "python"
        };

        foreach (var cand in pythonCandidates)
        {
            if (cand == "python" || File.Exists(cand))
            {
                return (cand, "-m uvicorn magang_log.server.app:create_app --factory --host 127.0.0.1 --port 8765");
            }
        }

        return null;
    }

    private static void TryStartBackendServer()
    {
        if (IsBackendHealthy())
        {
            return;
        }

        try
        {
            var baseDir = AppDomain.CurrentDomain.BaseDirectory;
            var workDir = ResolveWorkDirectory(baseDir);
            var command = ResolveBackendCommand(baseDir, workDir);
            if (command == null)
            {
                return;
            }

            var psi = new ProcessStartInfo
            {
                FileName = command.Value.FileName,
                Arguments = command.Value.Arguments,
                WorkingDirectory = workDir,
                CreateNoWindow = true,
                UseShellExecute = false,
                WindowStyle = ProcessWindowStyle.Hidden
            };
            _backendProcess = Process.Start(psi);

            var deadline = DateTime.UtcNow.AddSeconds(10);
            while (DateTime.UtcNow < deadline)
            {
                if (_backendProcess == null || _backendProcess.HasExited)
                {
                    break;
                }
                if (IsBackendHealthy())
                {
                    break;
                }
                Thread.Sleep(150);
            }
        }
        catch
        {
            // Jika backend gagal dijalankan, biarkan form menampilkan status offline
        }
    }

    private static void TryStopBackendServer()
    {
        try
        {
            if (_backendProcess != null && !_backendProcess.HasExited)
            {
                _backendProcess.Kill(entireProcessTree: true);
                _backendProcess.Dispose();
                _backendProcess = null;
            }
        }
        catch
        {
            // Suppress errors during shutdown
        }
    }
}
