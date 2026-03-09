param(
    [string]$BaseUrl = $env:BASE_URL,
    [string]$User = $env:USER_ID,
    [string]$Query = $env:QUERY,
    [string]$ResponseMode = $(if ($env:RESPONSE_MODE) { $env:RESPONSE_MODE } else { "streaming" }),
    [string]$ConversationId = $env:CONVERSATION_ID,
    [string]$InputsJson = $env:INPUTS_JSON
)

[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding
Add-Type -AssemblyName System.Net.Http

if (-not $BaseUrl) {
    $BaseUrl = "http://127.0.0.1:8000"
}

if (-not $User) {
    $User = "u10001"
}

if (-not $Query) {
    $Query = "Hello"
}

if (-not $InputsJson) {
    $InputsJson = "{}"
}

$inputs = $InputsJson | ConvertFrom-Json

$requestBody = @{
    inputs = $inputs
    query = $Query
    user = $User
    response_mode = $ResponseMode
}

if ($ConversationId) {
    $requestBody.conversation_id = $ConversationId
}

$jsonBody = $requestBody | ConvertTo-Json -Depth 10
$bodyBytes = [System.Text.Encoding]::UTF8.GetBytes($jsonBody)
$requestUri = "$BaseUrl/chat/completion"

if ($ResponseMode -eq "blocking") {
    $headers = @{
        "Content-Type" = "application/json; charset=utf-8"
        "Accept" = "application/json; charset=utf-8"
    }

    $response = Invoke-RestMethod `
        -Method Post `
        -Uri $requestUri `
        -Headers $headers `
        -Body $bodyBytes

    $response | ConvertTo-Json -Depth 10
    return
}

$handler = $null
$client = $null
$request = $null
$response = $null
$stream = $null
$reader = $null

$handler = New-Object System.Net.Http.HttpClientHandler
$client = New-Object System.Net.Http.HttpClient($handler)

try {
    $request = New-Object System.Net.Http.HttpRequestMessage([System.Net.Http.HttpMethod]::Post, $requestUri)
    $request.Headers.Accept.ParseAdd("text/event-stream")
    $request.Content = New-Object System.Net.Http.ByteArrayContent -ArgumentList @(, $bodyBytes)
    $request.Content.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse("application/json; charset=utf-8")

    $response = $client.SendAsync(
        $request,
        [System.Net.Http.HttpCompletionOption]::ResponseHeadersRead
    ).GetAwaiter().GetResult()

    $response.EnsureSuccessStatusCode()

    $stream = $response.Content.ReadAsStreamAsync().GetAwaiter().GetResult()
    $reader = [System.IO.StreamReader]::new($stream, [System.Text.Encoding]::UTF8)

    while (-not $reader.EndOfStream) {
        $line = $reader.ReadLine()
        if ($null -ne $line) {
            Write-Output $line
        }
    }
}
finally {
    if ($reader) { $reader.Dispose() }
    if ($stream) { $stream.Dispose() }
    if ($response) { $response.Dispose() }
    if ($request) { $request.Dispose() }
    if ($client) { $client.Dispose() }
    if ($handler) { $handler.Dispose() }
}
