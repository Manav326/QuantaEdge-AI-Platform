$ErrorActionPreference = "Stop"

$secretDirectory = "D:\QuantaEdgeAI\secrets"
$tokenPath = Join-Path $secretDirectory "cloudflare-tunnel.token"
$secureToken = Read-Host "Paste the Cloudflare Tunnel token" -AsSecureString

if ($secureToken.Length -lt 40) {
    throw "The tunnel token looks too short. Copy the full token from the Cloudflare dashboard."
}

$pointer = [IntPtr]::Zero
$plainToken = $null
try {
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)
    $plainToken = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)

    New-Item -ItemType Directory -Force -Path $secretDirectory | Out-Null
    [System.IO.File]::WriteAllText(
        $tokenPath,
        $plainToken,
        (New-Object System.Text.UTF8Encoding($false))
    )
}
finally {
    if ($pointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
    $plainToken = $null
    if ($secureToken) { $secureToken.Dispose() }
}

$account = "$env:USERDOMAIN\$env:USERNAME"
$accountGrant = $account + ":(OI)(CI)F"
& icacls.exe $secretDirectory /inheritance:r /grant:r `
    $accountGrant `
    "NT AUTHORITY\SYSTEM:(OI)(CI)F" `
    "BUILTIN\Administrators:(OI)(CI)F" /T | Out-Host

if ($LASTEXITCODE -ne 0) {
    throw "Could not restrict the tunnel-token folder permissions. Check the folder ACL before starting the connector."
}

Write-Host "Cloudflare Tunnel token saved outside the repository:" -ForegroundColor Green
Write-Host $tokenPath
Write-Host "Only the current user, SYSTEM and local Administrators have folder access."