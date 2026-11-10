using System.Diagnostics;
using System.IO;
using System.Net.Http;
using System.Threading;
using MagangLog.Desktop.Forms;

namespace MagangLog.Desktop;

internal static class Program
{
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

    private static void TryStartBackendServer()
    {
        try
        {
            // Cek apakah server lokal di port 8765 sudah aktif
            using var client = new HttpClient { Timeout = TimeSpan.FromMilliseconds(400) };
            var res = client.GetAsync("http://127.0.0.1:8765/api/setup/requirements").GetAwaiter().GetResult();
            if (res.IsSuccessStatusCode)
            {
                return; // Server sudah aktif
            }
        }
        catch
        {
            // Server belum aktif, lanjutkan ke inisialisasi background runner
        }

        try
        {
            var baseDir = AppDomain.CurrentDomain.BaseDirectory;
            string? pythonExe = null;
            var candidates = new[]
            {
                Path.Combine(baseDir, ".venv", "Scripts", "python.exe"),
                Path.Combine(baseDir, "..", ".venv", "Scripts", "python.exe"),
                Path.Combine(baseDir, "..", "..", ".venv", "Scripts", "python.exe"),
                Path.Combine(baseDir, "venv", "Scripts", "python.exe"),
                "python"
            };

            foreach (var cand in candidates)
            {
                if (cand == "python" || File.Exists(cand))
                {
                    pythonExe = cand;
                    break;
                }
            }

            if (pythonExe != null)
            {
                // Tentukan working directory proyek yang memuat pyproject.toml / src
                var workDir = baseDir;
                if (!File.Exists(Path.Combine(workDir, "pyproject.toml")))
                {
                    var parent = Directory.GetParent(baseDir)?.FullName;
                    if (parent != null && File.Exists(Path.Combine(parent, "pyproject.toml")))
                    {
                        workDir = parent;
                    }
                    else
                    {
                        var rootDir = Directory.GetParent(parent ?? "")?.FullName;
                        if (rootDir != null && File.Exists(Path.Combine(rootDir, "pyproject.toml")))
                        {
                            workDir = rootDir;
                        }
                    }
                }

                var psi = new ProcessStartInfo
                {
                    FileName = pythonExe,
                    Arguments = "-m uvicorn magang_log.server.app:create_app --factory --host 127.0.0.1 --port 8765",
                    WorkingDirectory = workDir,
                    CreateNoWindow = true,
                    UseShellExecute = false,
                    WindowStyle = ProcessWindowStyle.Hidden
                };
                _backendProcess = Process.Start(psi);
                Thread.Sleep(800); // Beri jeda sejenak untuk bind socket server
            }
        }
        catch
        {
            // Jika Python belum terpasang atau gagal spawn, biarkan form menampilkan status offline
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
