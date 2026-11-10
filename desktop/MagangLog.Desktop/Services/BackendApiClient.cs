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

    /// <summary>
    /// Persist complete configuration payload via POST /api/setup/save.
    /// </summary>
    public virtual async Task<SaveConfigResponse> SaveConfigAsync(
        SaveConfigRequest request,
        CancellationToken cancellationToken = default)
    {
        var jsonPayload = JsonSerializer.Serialize(request, JsonOptions);
        var content = new StringContent(jsonPayload, Encoding.UTF8, "application/json");

        var response = await _httpClient.PostAsync($"{_baseUrl}/api/setup/save", content, cancellationToken);
        response.EnsureSuccessStatusCode();

        var json = await response.Content.ReadAsStringAsync(cancellationToken);
        return JsonSerializer.Deserialize<SaveConfigResponse>(json, JsonOptions)
               ?? new SaveConfigResponse { Success = true };
    }

    /// <summary>
    /// Fetch today's pipeline, gate, and ledger status via GET /api/status/today.
    /// Returns null if network fails or backend is unreachable.
    /// </summary>
    public virtual async Task<TodayStatusResponse?> GetTodayStatusAsync(
        string? dateStr = null,
        CancellationToken cancellationToken = default)
    {
        try
        {
            var url = string.IsNullOrWhiteSpace(dateStr)
                ? $"{_baseUrl}/api/status/today"
                : $"{_baseUrl}/api/status/today?date={Uri.EscapeDataString(dateStr)}";

            var response = await _httpClient.GetAsync(url, cancellationToken);
            if (!response.IsSuccessStatusCode)
            {
                return null;
            }

            var json = await response.Content.ReadAsStringAsync(cancellationToken);
            return JsonSerializer.Deserialize<TodayStatusResponse>(json, JsonOptions);
        }
        catch (Exception)
        {
            return null;
        }
    }

    /// <summary>
    /// Trigger manual pipeline execution (draft regeneration from evidence) via POST /api/entry/draft.
    /// Returns true if execution succeeded, false otherwise.
    /// </summary>
    public virtual async Task<bool> TriggerPipelineAsync(
        string? dateStr = null,
        CancellationToken cancellationToken = default)
    {
        try
        {
            var payload = new Dictionary<string, string>();
            if (!string.IsNullOrWhiteSpace(dateStr))
            {
                payload["work_date"] = dateStr;
            }

            var jsonPayload = JsonSerializer.Serialize(payload, JsonOptions);
            var content = new StringContent(jsonPayload, Encoding.UTF8, "application/json");

            var response = await _httpClient.PostAsync($"{_baseUrl}/api/entry/draft", content, cancellationToken);
            return response.IsSuccessStatusCode;
        }
        catch (Exception)
        {
            return false;
        }
    }

    /// <summary>
    /// Fetch sanitized evidence timeline items for today via GET /api/evidence/today.
    /// Returns empty list if network fails or backend is unreachable.
    /// </summary>
    public virtual async Task<List<EvidenceItem>> GetEvidenceTodayAsync(
        string? dateStr = null,
        CancellationToken cancellationToken = default)
    {
        try
        {
            var url = string.IsNullOrWhiteSpace(dateStr)
                ? $"{_baseUrl}/api/evidence/today"
                : $"{_baseUrl}/api/evidence/today?date={Uri.EscapeDataString(dateStr)}";

            var response = await _httpClient.GetAsync(url, cancellationToken);
            if (!response.IsSuccessStatusCode)
            {
                return new List<EvidenceItem>();
            }

            var json = await response.Content.ReadAsStringAsync(cancellationToken);
            var feed = JsonSerializer.Deserialize<EvidenceFeedResponse>(json, JsonOptions);
            return feed?.Items ?? new List<EvidenceItem>();
        }
        catch (Exception)
        {
            return new List<EvidenceItem>();
        }
    }

    /// <summary>
    /// Fetch today's active entry details via GET /api/entry/today.
    /// Returns null if not found (404) or on network failure.
    /// </summary>
    public virtual async Task<EntryDetailResponse?> GetTodayEntryAsync(
        string? dateStr = null,
        CancellationToken cancellationToken = default)
    {
        try
        {
            var url = string.IsNullOrWhiteSpace(dateStr)
                ? $"{_baseUrl}/api/entry/today"
                : $"{_baseUrl}/api/entry/today?date={Uri.EscapeDataString(dateStr)}";

            var response = await _httpClient.GetAsync(url, cancellationToken);
            if (!response.IsSuccessStatusCode)
            {
                return null;
            }

            var json = await response.Content.ReadAsStringAsync(cancellationToken);
            return JsonSerializer.Deserialize<EntryDetailResponse>(json, JsonOptions);
        }
        catch (Exception)
        {
            return null;
        }
    }

    /// <summary>
    /// Save inline draft edits via POST /api/entry/edit.
    /// </summary>
    public virtual async Task<EditEntryResponse?> EditEntryAsync(
        EditEntryRequest request,
        CancellationToken cancellationToken = default)
    {
        try
        {
            var jsonPayload = JsonSerializer.Serialize(request, JsonOptions);
            var content = new StringContent(jsonPayload, Encoding.UTF8, "application/json");

            var response = await _httpClient.PostAsync($"{_baseUrl}/api/entry/edit", content, cancellationToken);
            if (!response.IsSuccessStatusCode)
            {
                return null;
            }

            var json = await response.Content.ReadAsStringAsync(cancellationToken);
            return JsonSerializer.Deserialize<EditEntryResponse>(json, JsonOptions);
        }
        catch (Exception)
        {
            return null;
        }
    }

    /// <summary>
    /// Request fresh Gemini AI draft via POST /api/entry/draft.
    /// </summary>
    public virtual async Task<DraftEntryResponse?> DraftEntryAsync(
        string? dateStr = null,
        CancellationToken cancellationToken = default)
    {
        try
        {
            var payload = new DraftEntryRequest { WorkDate = dateStr };
            var jsonPayload = JsonSerializer.Serialize(payload, JsonOptions);
            var content = new StringContent(jsonPayload, Encoding.UTF8, "application/json");

            var response = await _httpClient.PostAsync($"{_baseUrl}/api/entry/draft", content, cancellationToken);
            if (!response.IsSuccessStatusCode)
            {
                return null;
            }

            var json = await response.Content.ReadAsStringAsync(cancellationToken);
            return JsonSerializer.Deserialize<DraftEntryResponse>(json, JsonOptions);
        }
        catch (Exception)
        {
            return null;
        }
    }

    /// <summary>
    /// Approve and submit validated draft to MagangHub portal via POST /api/entry/approve.
    /// </summary>
    public virtual async Task<ApproveEntryResponse?> ApproveEntryAsync(
        string? dateStr = null,
        bool dryRun = false,
        CancellationToken cancellationToken = default)
    {
        try
        {
            var payload = new ApproveEntryRequest { WorkDate = dateStr, DryRun = dryRun };
            var jsonPayload = JsonSerializer.Serialize(payload, JsonOptions);
            var content = new StringContent(jsonPayload, Encoding.UTF8, "application/json");

            var response = await _httpClient.PostAsync($"{_baseUrl}/api/entry/approve", content, cancellationToken);
            if (!response.IsSuccessStatusCode)
            {
                return null;
            }

            var json = await response.Content.ReadAsStringAsync(cancellationToken);
            return JsonSerializer.Deserialize<ApproveEntryResponse>(json, JsonOptions);
        }
        catch (Exception)
        {
            return null;
        }
    }

    /// <summary>
    /// Submit manual reflection note via POST /api/notes (ADR-0003).
    /// </summary>
    public virtual async Task<CreateNoteResponse?> PostNoteAsync(
        CreateNoteRequest request,
        CancellationToken cancellationToken = default)
    {
        try
        {
            var jsonPayload = JsonSerializer.Serialize(request, JsonOptions);
            var content = new StringContent(jsonPayload, Encoding.UTF8, "application/json");

            var response = await _httpClient.PostAsync($"{_baseUrl}/api/notes", content, cancellationToken);
            if (!response.IsSuccessStatusCode)
            {
                return null;
            }

            var json = await response.Content.ReadAsStringAsync(cancellationToken);
            return JsonSerializer.Deserialize<CreateNoteResponse>(json, JsonOptions);
        }
        catch (Exception)
        {
            return null;
        }
    }

    /// <summary>
    /// Fetches logbook entry compliance statuses for all days in a month via GET /api/calendar/month.
    /// </summary>
    public virtual async Task<MonthCalendarResponse?> GetCalendarMonthAsync(
        int year,
        int month,
        CancellationToken cancellationToken = default)
    {
        try
        {
            var response = await _httpClient.GetAsync($"{_baseUrl}/api/calendar/month?year={year}&month={month}", cancellationToken);
            if (!response.IsSuccessStatusCode)
            {
                return null;
            }

            var json = await response.Content.ReadAsStringAsync(cancellationToken);
            return JsonSerializer.Deserialize<MonthCalendarResponse>(json, JsonOptions);
        }
        catch (Exception)
        {
            return null;
        }
    }

    /// <summary>
    /// Fetches active application configuration via GET /api/setup/config.
    /// </summary>
    public virtual async Task<SaveConfigRequest?> GetAppConfigAsync(
        string? configPath = null,
        CancellationToken cancellationToken = default)
    {
        try
        {
            var url = string.IsNullOrWhiteSpace(configPath)
                ? $"{_baseUrl}/api/setup/config"
                : $"{_baseUrl}/api/setup/config?config_path={Uri.EscapeDataString(configPath)}";

            var response = await _httpClient.GetAsync(url, cancellationToken);
            if (!response.IsSuccessStatusCode)
            {
                return null;
            }

            var json = await response.Content.ReadAsStringAsync(cancellationToken);
            return JsonSerializer.Deserialize<SaveConfigRequest>(json, JsonOptions);
        }
        catch (Exception)
        {
            return null;
        }
    }

    /// <summary>
    /// Inspects Windows Task Scheduler registration status via GET /api/setup/scheduler-status.
    /// </summary>
    public virtual async Task<SchedulerStatusResponse?> GetSchedulerStatusAsync(
        string taskPrefix = "MagangLog",
        CancellationToken cancellationToken = default)
    {
        try
        {
            var url = $"{_baseUrl}/api/setup/scheduler-status?task_prefix={Uri.EscapeDataString(taskPrefix)}";
            var response = await _httpClient.GetAsync(url, cancellationToken);
            if (!response.IsSuccessStatusCode)
            {
                return null;
            }

            var json = await response.Content.ReadAsStringAsync(cancellationToken);
            return JsonSerializer.Deserialize<SchedulerStatusResponse>(json, JsonOptions);
        }
        catch (Exception)
        {
            return null;
        }
    }

    /// <summary>
    /// Registers background automation in Windows Task Scheduler via POST /api/setup/register-scheduler.
    /// </summary>
    public virtual async Task<RegisterSchedulerResponse?> RegisterSchedulerAsync(
        RegisterSchedulerRequest request,
        CancellationToken cancellationToken = default)
    {
        try
        {
            var jsonPayload = JsonSerializer.Serialize(request, JsonOptions);
            var content = new StringContent(jsonPayload, Encoding.UTF8, "application/json");

            var response = await _httpClient.PostAsync($"{_baseUrl}/api/setup/register-scheduler", content, cancellationToken);
            if (!response.IsSuccessStatusCode)
            {
                return null;
            }

            var json = await response.Content.ReadAsStringAsync(cancellationToken);
            return JsonSerializer.Deserialize<RegisterSchedulerResponse>(json, JsonOptions);
        }
        catch (Exception)
        {
            return null;
        }
    }

    /// <summary>
    /// Unregisters background automation from Windows Task Scheduler via POST /api/setup/unregister-scheduler.
    /// </summary>
    public virtual async Task<UnregisterSchedulerResponse?> UnregisterSchedulerAsync(
        string taskPrefix = "MagangLog",
        CancellationToken cancellationToken = default)
    {
        try
        {
            var payload = new UnregisterSchedulerRequest { TaskPrefix = taskPrefix };
            var jsonPayload = JsonSerializer.Serialize(payload, JsonOptions);
            var content = new StringContent(jsonPayload, Encoding.UTF8, "application/json");

            var response = await _httpClient.PostAsync($"{_baseUrl}/api/setup/unregister-scheduler", content, cancellationToken);
            if (!response.IsSuccessStatusCode)
            {
                return null;
            }

            var json = await response.Content.ReadAsStringAsync(cancellationToken);
            return JsonSerializer.Deserialize<UnregisterSchedulerResponse>(json, JsonOptions);
        }
        catch (Exception)
        {
            return null;
        }
    }

    /// <summary>
    /// Tests Gemini API key validity via POST /api/setup/test-gemini.
    /// </summary>
    public virtual async Task<TestGeminiResponse?> TestGeminiAsync(
        string apiKey,
        CancellationToken cancellationToken = default)
    {
        try
        {
            var payload = new TestGeminiRequest { ApiKey = apiKey };
            var jsonPayload = JsonSerializer.Serialize(payload, JsonOptions);
            var content = new StringContent(jsonPayload, Encoding.UTF8, "application/json");

            var response = await _httpClient.PostAsync($"{_baseUrl}/api/setup/test-gemini", content, cancellationToken);
            if (!response.IsSuccessStatusCode)
            {
                return new TestGeminiResponse { Valid = false, Model = string.Empty };
            }

            var json = await response.Content.ReadAsStringAsync(cancellationToken);
            return JsonSerializer.Deserialize<TestGeminiResponse>(json, JsonOptions)
                   ?? new TestGeminiResponse { Valid = false };
        }
        catch (Exception)
        {
            return new TestGeminiResponse { Valid = false, Model = string.Empty };
        }
    }

    /// <summary>
    /// Checks current MagangHub portal authentication session status via GET /api/portal/auth-status.
    /// </summary>
    public virtual async Task<PortalAuthStatusResponse?> GetPortalAuthStatusAsync(
        CancellationToken cancellationToken = default)
    {
        try
        {
            var response = await _httpClient.GetAsync($"{_baseUrl}/api/portal/auth-status", cancellationToken);
            if (!response.IsSuccessStatusCode)
            {
                return new PortalAuthStatusResponse { Authenticated = false, SessionStatus = "missing" };
            }

            var json = await response.Content.ReadAsStringAsync(cancellationToken);
            return JsonSerializer.Deserialize<PortalAuthStatusResponse>(json, JsonOptions)
                   ?? new PortalAuthStatusResponse { Authenticated = false, SessionStatus = "missing" };
        }
        catch (Exception)
        {
            return new PortalAuthStatusResponse { Authenticated = false, SessionStatus = "missing" };
        }
    }

    /// <summary>
    /// Launches interactive login browser for portal Monev Kemnaker via POST /api/portal/open-login.
    /// </summary>
    public virtual async Task<OpenLoginResponse?> OpenPortalLoginAsync(
        int timeoutSeconds = 300,
        CancellationToken cancellationToken = default)
    {
        try
        {
            var payload = new OpenLoginRequest { TimeoutSeconds = timeoutSeconds };
            var jsonPayload = JsonSerializer.Serialize(payload, JsonOptions);
            var content = new StringContent(jsonPayload, Encoding.UTF8, "application/json");

            var response = await _httpClient.PostAsync($"{_baseUrl}/api/portal/open-login", content, cancellationToken);
            if (!response.IsSuccessStatusCode)
            {
                return new OpenLoginResponse { Success = false, Message = "Gagal meluncurkan browser login.", Authenticated = false };
            }

            var json = await response.Content.ReadAsStringAsync(cancellationToken);
            return JsonSerializer.Deserialize<OpenLoginResponse>(json, JsonOptions)
                   ?? new OpenLoginResponse { Success = false };
        }
        catch (Exception ex)
        {
            return new OpenLoginResponse { Success = false, Message = ex.Message, Authenticated = false };
        }
    }
}
