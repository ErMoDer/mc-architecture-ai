# Push mc-architecture-ai to GitHub. UTF-8, called by push_to_github.cmd.
$ErrorActionPreference = 'Stop'
$repo = 'https://github.com/ErMoDer/mc-architecture-ai.git'
$proj = 'C:\Users\16119\Desktop\ai agent\mc-architecture-ai'
Set-Location $proj

Write-Host '=== Push mc-architecture-ai to GitHub ===' -ForegroundColor Cyan
Write-Host ''

# Token: prefer env var GITHUB_TOKEN, else prompt
$token = $env:GITHUB_TOKEN
if (-not $token) {
    Write-Host '[INFO] GITHUB_TOKEN env var not set' -ForegroundColor Yellow
    $secure = Read-Host -AsSecureString 'Paste your GitHub Personal Access Token (ghp_...)'
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    $token = [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    Write-Host ''
}
if (-not $token) {
    Write-Host '[ERROR] No token, aborting.' -ForegroundColor Red
    exit 1
}

Write-Host '=== Check uncommitted changes ===' -ForegroundColor Cyan
$changes = git status --porcelain
if ($changes) {
    $changes | ForEach-Object { Write-Host $_ }
    Write-Host ''
    $ans = Read-Host 'Uncommitted changes found. Commit before push? (y/n)'
    if ($ans -ieq 'y') {
        $msg = Read-Host 'Commit message (default: update)'
        if (-not $msg) { $msg = 'update' }
        git add -A
        if ($LASTEXITCODE -ne 0) { Write-Host 'git add failed' -ForegroundColor Red; exit 1 }
        git commit -m $msg
        if ($LASTEXITCODE -ne 0) { Write-Host 'commit failed' -ForegroundColor Red; exit 1 }
    }
} else {
    Write-Host 'Working tree clean.'
}
Write-Host ''

Write-Host '=== Push main branch ===' -ForegroundColor Cyan
$pushUrl = "https://x-access-token:$token@github.com/ErMoDer/mc-architecture-ai.git"
git push $pushUrl main
if ($LASTEXITCODE -ne 0) {
    Write-Host '[ERROR] push failed. Check token scope (repo) or network.' -ForegroundColor Red
    exit 1
}

Write-Host ''
Write-Host '=== Done ===' -ForegroundColor Green
Write-Host "Repo: $repo" -ForegroundColor Green
