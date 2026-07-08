# Waits until the dashboard is serving, then opens it in the default browser.
# Called in the background by "Start Trading Bot.bat".
$url = 'http://localhost:8000'
for ($i = 0; $i -lt 180; $i++) {
    try {
        Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2 | Out-Null
        Start-Process $url
        exit 0
    } catch {
        Start-Sleep -Seconds 1
    }
}
# Fallback: open anyway after ~3 minutes so the user at least gets a tab.
Start-Process $url
