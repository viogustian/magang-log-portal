using System.Net;

namespace MagangLog.Desktop.Tests;

public class MockHttpMessageHandler : HttpMessageHandler
{
    private readonly Func<HttpRequestMessage, HttpResponseMessage> _handler;

    public List<HttpRequestMessage> SentRequests { get; } = new();

    public MockHttpMessageHandler(Func<HttpRequestMessage, HttpResponseMessage> handler)
    {
        _handler = handler;
    }

    public MockHttpMessageHandler(string jsonResponse, HttpStatusCode statusCode = HttpStatusCode.OK)
    {
        _handler = _ => new HttpResponseMessage(statusCode)
        {
            Content = new StringContent(jsonResponse, System.Text.Encoding.UTF8, "application/json")
        };
    }

    protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
    {
        SentRequests.Add(request);
        return Task.FromResult(_handler(request));
    }
}

