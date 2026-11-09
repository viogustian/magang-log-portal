using System.Text.Json;
using System.Text.Json.Serialization;

namespace MagangLog.Desktop.Models;

/// <summary>
/// Tracks SetupWizard progression state, completed steps, and partial form data across sessions.
/// </summary>
public class WizardProgressState
{
    [JsonPropertyName("current_step")]
    public int CurrentStep { get; set; } = 0;

    [JsonPropertyName("completed_steps")]
    public List<int> CompletedSteps { get; set; } = new();

    [JsonPropertyName("project_folders")]
    public List<string> ProjectFolders { get; set; } = new();

    [JsonPropertyName("role_description")]
    public string RoleDescription { get; set; } = string.Empty;

    [JsonPropertyName("profile_name")]
    public string ProfileName { get; set; } = string.Empty;

    [JsonPropertyName("keywords")]
    public List<string> Keywords { get; set; } = new();

    [JsonPropertyName("sources")]
    public SourcesConfig Sources { get; set; } = new();

    [JsonPropertyName("review_mode")]
    public string ReviewMode { get; set; } = "review";

    [JsonPropertyName("full_access_confirmed")]
    public bool FullAccessConfirmed { get; set; } = false;

    [JsonPropertyName("step_data")]
    public Dictionary<string, object?> StepData { get; set; } = new();

    public void MarkStepCompleted(int stepIndex)
    {
        if (!CompletedSteps.Contains(stepIndex))
        {
            CompletedSteps.Add(stepIndex);
            CompletedSteps.Sort();
        }
    }

    public void SetStepData(string key, object? value)
    {
        StepData[key] = value;
    }

    public T? GetStepData<T>(string key)
    {
        if (StepData.TryGetValue(key, out var val) && val is not null)
        {
            if (val is JsonElement elem)
            {
                return JsonSerializer.Deserialize<T>(elem.GetRawText());
            }
            if (val is T typed)
            {
                return typed;
            }
            var json = JsonSerializer.Serialize(val);
            return JsonSerializer.Deserialize<T>(json);
        }
        return default;
    }

    public int GetNextIncompleteStep(int totalSteps = 6)
    {
        for (int i = 0; i < totalSteps; i++)
        {
            if (!CompletedSteps.Contains(i))
            {
                return i;
            }
        }
        return totalSteps - 1;
    }
}

public class SaveProgressResponse
{
    [JsonPropertyName("success")]
    public bool Success { get; set; }

    [JsonPropertyName("saved_at")]
    public string SavedAt { get; set; } = string.Empty;
}

