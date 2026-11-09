$ErrorActionPreference = "Stop"

$secretDirectory = "D:\QuantaEdgeAI\secrets"
$tokenPath = Join-Path $secretDirectory "cloudflare-tunnel.token"
$volume = "quantaedge-cloudflare-tunnel-token"
$secureToken = Read-Host "Paste the Cloudflare Tunnel token" -AsSecureString
$process = $null

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

    $account = "$env:USERDOMAIN\$env:USERNAME"
    $accountGrant = $account + ":(OI)(CI)F"
    & icacls.exe $secretDirectory /inheritance:r /grant:r `
        $accountGrant `
        "NT AUTHORITY\SYSTEM:(OI)(CI)F" `
        "BUILTIN\Administrators:(OI)(CI)F" /T | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "Could not restrict the tunnel-token folder permissions."
    }

    & docker volume create $volume | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Could not create the Docker-managed tunnel-token volume."
    }

    # Pull the small provisioning image before opening redirected pipes.
    & docker pull alpine:3.20 | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "Could not pull the Alpine provisioning image."
    }

    # cloudflare/cloudflared runs as UID/GID 65532. Set the volume file
    # to that owner and mode 0400 so only that container identity can read it.
    # The token itself travels over stdin, never in Docker args or environment.
    $containerCommand = 'umask 077; cat > /run/secrets/cloudflare_tunnel_token && chown 65532:65532 /run/secrets/cloudflare_tunnel_token && chmod 0400 /run/secrets/cloudflare_tunnel_token'
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = (Get-Command docker).Source
    $startInfo.Arguments = "run --pull=never -i --rm --mount type=volume,source=$volume,target=/run/secrets alpine:3.20 sh -c `"$containerCommand`""
    $startInfo.UseShellExecute = $false
    $startInfo.RedirectStandardInput = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.CreateNoWindow = $true

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $startInfo
    if (-not $process.Start()) {
        throw "Could not start Docker to provision the tunnel-token volume."
    }

    $process.StandardInput.Write($plainToken)
    $process.StandardInput.Close()
    $stdout = $process.StandardOutput.ReadToEnd()
    $stderr = $process.StandardError.ReadToEnd()
    $process.WaitForExit()
    if ($process.ExitCode -ne 0) {
        throw "Could not write the tunnel token into the Docker volume. $stderr"
    }
}
finally {
    if ($pointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
    $plainToken = $null
    if ($secureToken) { $secureToken.Dispose() }
    if ($process) { $process.Dispose() }
}

Write-Host "Cloudflare Tunnel token saved locally and provisioned in Docker volume:" -ForegroundColor Green
Write-Host $tokenPath
Write-Host "Docker volume: $volume (readable only by cloudflared UID 65532)"
Write-Host "The token is not stored in Git, Compose environment variables, or container arguments."
