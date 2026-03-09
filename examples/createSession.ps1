param(
    [string]$BaseUrl = $env:BASE_URL,
    [string]$UserId = $env:USER_ID,
    [string]$Title = $env:TITLE,
    [int]$ExpireSeconds = $(if ($env:EXPIRE_SECONDS) { [int]$env:EXPIRE_SECONDS } else { 1200 })
)

[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding

if (-not $BaseUrl) {
    $BaseUrl = "http://127.0.0.1:8000"
}

if (-not $UserId) {
    $UserId = "u10001"
}

if (-not $Title) {
    $Title = -join ([char[]](0x65B0, 0x5EFA, 0x4F1A, 0x8BDD))
}

$headers = @{
    "Content-Type" = "application/json; charset=utf-8"
    "Accept" = "application/json; charset=utf-8"
}

$body = @{
    user_id = $UserId
    title = $Title
    expire_seconds = $ExpireSeconds
    client_capabilities = @("web_search", "vision")
    metadata = @{
        source = "powershell-example"
    }
} | ConvertTo-Json -Depth 4

$bodyBytes = [System.Text.Encoding]::UTF8.GetBytes($body)

$response = Invoke-RestMethod `
    -Method Post `
    -Uri "$BaseUrl/chat/create" `
    -Headers $headers `
    -Body $bodyBytes

$response | ConvertTo-Json -Depth 10
