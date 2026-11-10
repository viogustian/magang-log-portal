using System.Net;
using MagangLog.Desktop.Controls;
using MagangLog.Desktop.Services;
using Xunit;

namespace MagangLog.Desktop.Tests;

public class GeminiCredentialsCardTests
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

    private static async Task RunStaAsync(Func<Task> action)
    {
        var tcs = new TaskCompletionSource();
        var thread = new Thread(async () =>
        {
            try
            {
                await action();
                tcs.SetResult();
            }
            catch (Exception e)
            {
                tcs.SetException(e);
            }
        });
        thread.SetApartmentState(ApartmentState.STA);
        thread.Start();
        await tcs.Task;
    }

    [Fact]
    public void TestInitialState_EmptyKeyDisablesReadyState()
    {
        RunSta(() =>
        {
            var handler = new MockHttpMessageHandler("{}");
            var client = new BackendApiClient(new HttpClient(handler));
            using var card = new GeminiCredentialsCard(client);

            card.ApiKey = string.Empty;
            Assert.False(card.IsKeyProvided);
            Assert.Equal("gemini-3.5-flash", card.SelectedModel);
            Assert.True(card.ApiKeyTextBox.UseSystemPasswordChar);
        });
    }

    [Fact]
    public void TestEnteringKey_UpdatesPropertyAndFiresGateStateChanged()
    {
        RunSta(() =>
        {
            var handler = new MockHttpMessageHandler("{}");
            var client = new BackendApiClient(new HttpClient(handler));
            using var card = new GeminiCredentialsCard(client);

            var fired = false;
            card.GateStateChanged += (_, _) => fired = true;

            card.ApiKey = "AIzaSyNewKey12345";

            Assert.True(card.IsKeyProvided);
            Assert.Equal("AIzaSyNewKey12345", card.ApiKey);
            Assert.True(fired);
        });
    }

    [Fact]
    public void TestShowHidePasswordToggle()
    {
        RunSta(() =>
        {
            var handler = new MockHttpMessageHandler("{}");
            var client = new BackendApiClient(new HttpClient(handler));
            using var card = new GeminiCredentialsCard(client);

            Assert.True(card.ApiKeyTextBox.UseSystemPasswordChar);
            card.ShowApiKeyCheckBox.Checked = true;
            Assert.False(card.ApiKeyTextBox.UseSystemPasswordChar);
            card.ShowApiKeyCheckBox.Checked = false;
            Assert.True(card.ApiKeyTextBox.UseSystemPasswordChar);
        });
    }

    [Fact]
    public async Task TestTestConnection_SuccessUpdatesStatus()
    {
        await RunStaAsync(async () =>
        {
            var responseJson = """{"valid": true, "model": "gemini-3.5-flash"}""";
            var handler = new MockHttpMessageHandler(responseJson);
            var client = new BackendApiClient(new HttpClient(handler));
            using var card = new GeminiCredentialsCard(client);

            card.ApiKey = "AIzaSyValidKey";
            var result = await card.TestConnectionAsync();

            Assert.True(result);
            Assert.True(card.IsTestedSuccessfully);
            Assert.Contains("valid", card.StatusLabel.Text.ToLower());
        });
    }

    [Fact]
    public async Task TestTestConnection_FailureUpdatesStatus()
    {
        await RunStaAsync(async () =>
        {
            var handler = new MockHttpMessageHandler(_ => new HttpResponseMessage(HttpStatusCode.BadGateway));
            var client = new BackendApiClient(new HttpClient(handler));
            using var card = new GeminiCredentialsCard(client);

            card.ApiKey = "AIzaSyInvalidKey";
            var result = await card.TestConnectionAsync();

            Assert.False(result);
            Assert.False(card.IsTestedSuccessfully);
            Assert.Contains("tidak valid", card.StatusLabel.Text.ToLower());
        });
    }

    [Fact]
    public async Task TestRefreshModels_PopulatesComboBox()
    {
        await RunStaAsync(async () =>
        {
            var responseJson = """
            {
                "models": [
                    {"id": "models/gemini-3.5-flash", "display_name": "Gemini 3.5 Flash", "is_recommended": true},
                    {"id": "models/gemini-3.8-flash", "display_name": "Gemini 3.8 Flash", "is_recommended": false}
                ],
                "active_model": "gemini-3.5-flash"
            }
            """;
            var handler = new MockHttpMessageHandler(responseJson);
            var client = new BackendApiClient(new HttpClient(handler));
            using var card = new GeminiCredentialsCard(client);

            card.ApiKey = "AIzaSyValidKey";
            await card.RefreshModelsAsync();

            Assert.Contains("gemini-3.5-flash", card.ModelComboBox.Items.Cast<string>());
            Assert.Contains("gemini-3.8-flash", card.ModelComboBox.Items.Cast<string>());
        });
    }

    [Fact]
    public void TestClickLink_InvokesUrlOpener()
    {
        RunSta(() =>
        {
            var handler = new MockHttpMessageHandler("{}");
            var client = new BackendApiClient(new HttpClient(handler));
            using var card = new GeminiCredentialsCard(client);

            string? openedUrl = null;
            card.UrlOpener = url => openedUrl = url;

            card.OpenApiKeyPortal();

            Assert.Equal("https://aistudio.google.com/app/apikey", openedUrl);
        });
    }
}
