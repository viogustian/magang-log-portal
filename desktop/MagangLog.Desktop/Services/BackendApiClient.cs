using System.Net.Http.Json;
using System.Text;
using System.Text.Json;
using MagangLog.Desktop.Models;

namespace MagangLog.Desktop.Services;

/// <summary>
/// HTTP client wrapper for communicating with the local FastAPI backend.
/// </summary>
public class BackendApiClient
{
    private readonly HttpClient _httpClient;
    private readonly string _baseUrl;

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true
    };

    public BackendApiClient(HttpClient? httpClient = null, string baseUrl = "http://127.0.0.1:8765")
    {
        _httpClient = httpClient ?? new HttpClient();
        _baseUrl = baseUrl.TrimEnd('/');
    }

    /// <summary>
    /// Fetch partial wizard progress from GET /api/setup/wizard-progress.
    /// </summary>
    public virtual async Task<WizardProgressState> GetWizardProgressAsync(CancellationToken cancellationToken = default)
    {
        try
        {
            var response = await _httpClient.GetAsync($"{_baseUrl}/api/setup/wizard-progress", cancellationToken);
            if (!response.IsSuccessStatusCode)
            {
                return new WizardProgressState();
            }

            var json = await response.Content.ReadAsStringAsync(cancellationToken);
            return JsonSerializer.Deserialize<WizardProgressState>(json, JsonOptions) ?? new WizardProgressState();
        }
        catch (Exception)
        {
            return new WizardProgressState();
        }
    }

    /// <summary>
    /// Persist partial wizard progress to POST /api/setup/save-progress.
    /// </summary>
    public virtual async Task<SaveProgressResponse> SaveWizardProgressAsync(
        WizardProgressState state,
        CancellationToken cancellationToken = default)
    {
        var jsonPayload = JsonSerializer.Serialize(state, JsonOptions);
        var content = new StringContent(jsonPayload, Encoding.UTF8, "application/json");

        var response = await _httpClient.PostAsync($"{_baseUrl}/api/setup/save-progress", content, cancellationToken);
        response.EnsureSuccessStatusCode();

        var json = await response.Content.ReadAsStringAsync(cancellationToken);
        return JsonSerializer.Deserialize<SaveProgressResponse>(json, JsonOptions)
               ?? new SaveProgressResponse { Success = true };
    }
}
