# Simple keep-alive script for Render free tier.
# Run this on a cron job (e.g., cron-job.org, GitHub Actions, or Task Scheduler)
# to ping the backend every 5 minutes and prevent cold starts.
#
# Usage:
#   .\scripts\keep-alive.ps1
#
# Or set up a free cron job at https://cron-job.org to hit:
#   https://ecoquery.onrender.com/api/health

$url = "https://ecoquery.onrender.com/api/health"
try {
    $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 10
    $status = $response.StatusCode
    $time = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Output "[$time] Pinged $url → $status"
} catch {
    $time = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Output "[$time] Pinged $url → FAILED: $_"
}
