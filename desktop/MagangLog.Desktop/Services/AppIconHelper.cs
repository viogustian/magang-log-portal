namespace MagangLog.Desktop.Services;

/// <summary>
/// Loads and caches the embedded application icon (<c>favicon.ico</c>) for forms and dialogs.
/// </summary>
public static class AppIconHelper
{
    public const string ResourceName = "MagangLog.Desktop.app.ico";

    private static readonly Lazy<byte[]?> IconBytes = new(LoadIconBytes);
    private static readonly Lazy<Icon?> SharedIcon = new(CreateSharedIcon);

    /// <summary>
    /// Returns the shared process-wide application icon loaded from the embedded resource.
    /// </summary>
    public static Icon? GetAppIcon() => SharedIcon.Value;

    /// <summary>
    /// Extracts a bitmap of the requested icon dimension for header/about badges.
    /// </summary>
    public static Bitmap? GetAppBitmap(int size = 48)
    {
        var bytes = IconBytes.Value;
        if (bytes == null || bytes.Length == 0)
        {
            return null;
        }

        try
        {
            using var ms = new MemoryStream(bytes);
            using var sized = new Icon(ms, new Size(size, size));
            return sized.ToBitmap();
        }
        catch
        {
            return null;
        }
    }

    /// <summary>
    /// Assigns the application icon to the specified WinForms window when available.
    /// </summary>
    public static void ApplyTo(Form form)
    {
        ArgumentNullException.ThrowIfNull(form);
        var icon = GetAppIcon();
        if (icon != null)
        {
            form.Icon = icon;
        }
    }

    private static byte[]? LoadIconBytes()
    {
        var assembly = typeof(AppIconHelper).Assembly;
        using var stream = assembly.GetManifestResourceStream(ResourceName);
        if (stream == null)
        {
            return null;
        }

        using var ms = new MemoryStream();
        stream.CopyTo(ms);
        return ms.ToArray();
    }

    private static Icon? CreateSharedIcon()
    {
        var bytes = IconBytes.Value;
        if (bytes != null && bytes.Length > 0)
        {
            try
            {
                using var ms = new MemoryStream(bytes);
                return new Icon(ms);
            }
            catch
            {
                // Fall through to executable icon extraction
            }
        }

        try
        {
            var exePath = Application.ExecutablePath;
            if (!string.IsNullOrWhiteSpace(exePath) && File.Exists(exePath))
            {
                return Icon.ExtractAssociatedIcon(exePath);
            }
        }
        catch
        {
            // Ignore in test/host environments without an extractable executable icon
        }

        return null;
    }
}

