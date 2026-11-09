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
    /// Fetch dynamic system requirements checklist from GET /api/setup/requirements.
    /// </summary>
    public virtual async Task<List<RequirementItem>> GetRequirementsAsync(CancellationToken cancellationToken = default)
    {
        try
        {
            var response = await _httpClient.GetAsync($"{_baseUrl}/api/setup/requirements", cancellationToken);
            if (!response.IsSuccessStatusCode)
            {
                return new List<RequirementItem>();
            }

            var json = await response.Content.ReadAsStringAsync(cancellationToken);
            return JsonSerializer.Deserialize<List<RequirementItem>>(json, JsonOptions) ?? new List<RequirementItem>();
        }
        catch (Exception)
        {
            return new List<RequirementItem>();
        }
    }

    /// <summary>
    /// Re-evaluate a single requirement by name via POST /api/setup/recheck-requirement.
    /// </summary>
    public virtual async Task<RequirementItem?> RecheckRequirementAsync(
        string name,
        CancellationToken cancellationToken = default)
    {
        var req = new RecheckRequirementRequest { Name = name };
        var jsonPayload = JsonSerializer.Serialize(req, JsonOptions);
        var content = new StringContent(jsonPayload, Encoding.UTF8, "application/json");

        var response = await _httpClient.PostAsync($"{_baseUrl}/api/setup/recheck-requirement", content, cancellationToken);
        if (!response.IsSuccessStatusCode)
        {
            return null;
        }

        var json = await response.Content.ReadAsStringAsync(cancellationToken);
        return JsonSerializer.Deserialize<RequirementItem>(json, JsonOptions);
    }

    /// <summary>
    /// Validate directory paths for existence, readability, and Git marker via POST /api/setup/validate-folders.
    /// </summary>
    public virtual async Task<List<FolderValidationResult>> ValidateFoldersAsync(
        IEnumerable<string> paths,
        CancellationToken cancellationToken = default)
    {
        var req = new ValidateFoldersRequest { Paths = paths.ToList() };
        var jsonPayload = JsonSerializer.Serialize(req, JsonOptions);
        var content = new StringContent(jsonPayload, Encoding.UTF8, "application/json");

        var response = await _httpClient.PostAsync($"{_baseUrl}/api/setup/validate-folders", content, cancellationToken);
        if (!response.IsSuccessStatusCode)
        {
            return new List<FolderValidationResult>();
        }

        var json = await response.Content.ReadAsStringAsync(cancellationToken);
        return JsonSerializer.Deserialize<List<FolderValidationResult>>(json, JsonOptions)
               ?? new List<FolderValidationResult>();
    }

    /// <summary>
    /// Predicts tailored WorkProfile and keywords from natural language description via POST /api/setup/predict-profile.
    /// </summary>
    public virtual async Task<PredictProfileResponse?> PredictProfileAsync(
        string description,
        string apiKey = "",
        CancellationToken cancellationToken = default)
    {
        var req = new PredictProfileRequest
        {
            Description = description,
            ApiKey = apiKey
        };
        var jsonPayload = JsonSerializer.Serialize(req, JsonOptions);
        var content = new StringContent(jsonPayload, Encoding.UTF8, "application/json");

        var response = await _httpClient.PostAsync($"{_baseUrl}/api/setup/predict-profile", content, cancellationToken);
        if (!response.IsSuccessStatusCode)
        {
            return null;
        }

        var json = await response.Content.ReadAsStringAsync(cancellationToken);
        return JsonSerializer.Deserialize<PredictProfileResponse>(json, JsonOptions);
    }

    /// <summary>
    /// Fetches standard offline WorkProfile presets via GET /api/setup/presets.
    /// </summary>
    public virtual async Task<List<WorkProfile>> GetPresetsAsync(CancellationToken cancellationToken = default)
    {
        try
        {
            var response = await _httpClient.GetAsync($"{_baseUrl}/api/setup/presets", cancellationToken);
            if (!response.IsSuccessStatusCode)
            {
                return new List<WorkProfile>();
            }

            var json = await response.Content.ReadAsStringAsync(cancellationToken);
            return JsonSerializer.Deserialize<List<WorkProfile>>(json, JsonOptions) ?? new List<WorkProfile>();
        }
        catch (Exception)
        {
            return new List<WorkProfile>();
        }
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
