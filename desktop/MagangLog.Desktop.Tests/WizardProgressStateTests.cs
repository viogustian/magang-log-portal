using System.Text.Json;
using MagangLog.Desktop.Models;
using Xunit;

namespace MagangLog.Desktop.Tests;

public class WizardProgressStateTests
{
    [Fact]
    public void TestDefaultStateProperties()
    {
        var state = new WizardProgressState();
        Assert.Equal(0, state.CurrentStep);
        Assert.Empty(state.CompletedSteps);
        Assert.Empty(state.StepData);
    }

    [Fact]
    public void TestSerializationRoundTrip()
    {
        var state = new WizardProgressState
        {
            CurrentStep = 2,
            CompletedSteps = new List<int> { 0, 1 },
            StepData = new Dictionary<string, object?>
            {
                ["role"] = "Software Engineer",
                ["folders"] = new[] { "C:/Repo1", "C:/Repo2" },
                ["is_git"] = true
            }
        };

        var json = JsonSerializer.Serialize(state);
        Assert.Contains("\"current_step\":2", json);
        Assert.Contains("\"completed_steps\":[0,1]", json);

        var restored = JsonSerializer.Deserialize<WizardProgressState>(json);
        Assert.NotNull(restored);
        Assert.Equal(2, restored.CurrentStep);
        Assert.Equal(new List<int> { 0, 1 }, restored.CompletedSteps);
        Assert.True(restored.StepData.ContainsKey("role"));
    }

    [Fact]
    public void TestMarkStepCompleted()
    {
        var state = new WizardProgressState();
        state.MarkStepCompleted(2);
        state.MarkStepCompleted(0);
        state.MarkStepCompleted(2); // duplicate should not duplicate entry

        Assert.Equal(new List<int> { 0, 2 }, state.CompletedSteps);
    }

    [Fact]
    public void TestGetNextIncompleteStep()
    {
        var state = new WizardProgressState();
        Assert.Equal(0, state.GetNextIncompleteStep(6));

        state.MarkStepCompleted(0);
        state.MarkStepCompleted(1);
        Assert.Equal(2, state.GetNextIncompleteStep(6));

        for (int i = 0; i < 6; i++)
        {
            state.MarkStepCompleted(i);
        }
        Assert.Equal(5, state.GetNextIncompleteStep(6));
    }
}

