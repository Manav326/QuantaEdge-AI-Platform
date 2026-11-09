[CmdletBinding()]
param(
    [ValidateSet("both", "hindi", "english")]
    [string]$Language = "both",

    [ValidateScript({ $_ -eq 0 -or ($_ -ge 6 -and $_ -le 12) })]
    [int]$ClassNo = 0,

    [string]$OutputRoot = "",

    [ValidatePattern("^[A-Za-z0-9][A-Za-z0-9-]{0,38}$")]
    [string]$ImageOwner = "manav326"
)

$ErrorActionPreference = "Stop"
$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$WorkspaceRoot = Split-Path -Parent (Split-Path -Parent $RepositoryRoot)
$ValidatorPath = Join-Path $PSScriptRoot "validate-ghcr-textbook-cache.py"

if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    if (-not [string]::IsNullOrWhiteSpace($env:QUANTAEDGE_TEXTBOOK_DOWNLOAD_DIR)) {
        $OutputRoot = $env:QUANTAEDGE_TEXTBOOK_DOWNLOAD_DIR
    }
    else {
        $OutputRoot = Join-Path $WorkspaceRoot "downloads\textbooks"
    }
}
$OutputRoot = [System.IO.Path]::GetFullPath($OutputRoot)
$ImageOwner = $ImageOwner.ToLowerInvariant()

function Invoke-NativeChecked {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,

        [switch]$CaptureOutput
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $nativePreferenceVariable = Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue
    $nativeOutput = @()
    $nativeExitCode = 0

    try {
        # PowerShell 7.3+ can turn native stderr into a terminating error before
        # $LASTEXITCODE is checked. Keep native exit codes authoritative instead.
        $ErrorActionPreference = "Continue"
        if ($nativePreferenceVariable) {
            $PSNativeCommandUseErrorActionPreference = $false
        }

        $nativeOutput = @(& $FilePath @Arguments 2>&1)
        $nativeExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    $outputText = ($nativeOutput | ForEach-Object { [string]$_ }) -join [Environment]::NewLine
    if ($nativeExitCode -ne 0) {
        $details = $outputText.Trim()
        if ([string]::IsNullOrWhiteSpace($details)) { $details = "No command output was returned." }
        throw ("Command failed with exit code $($nativeExitCode): $FilePath $($Arguments -join ' ')" + [Environment]::NewLine + $details)
    }

    if ($CaptureOutput) {
        return $outputText.Trim()
    }

    if (-not [string]::IsNullOrWhiteSpace($outputText)) {
        Write-Host $outputText
    }
}

if (-not (Test-Path -LiteralPath $ValidatorPath -PathType Leaf)) {
    throw "The repository validator is missing: $ValidatorPath. Run git pull from the knowledge-engine repository first."
}

$dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
if (-not $dockerCommand) {
    throw "Docker CLI was not found. Install/start Docker Desktop, then reopen PowerShell."
}
$dockerPath = if ($dockerCommand.Source) { $dockerCommand.Source } else { $dockerCommand.Path }
if ([string]::IsNullOrWhiteSpace($dockerPath)) { $dockerPath = "docker" }

$venvPython = Join-Path $RepositoryRoot ".venv\Scripts\python.exe"
if (Test-Path -LiteralPath $venvPython -PathType Leaf) {
    $pythonPath = $venvPython
}
else {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCommand) {
        throw "Python was not found. Install Python 3.12 or run scripts\initialize.ps1 first."
    }
    $pythonPath = if ($pythonCommand.Source) { $pythonCommand.Source } else { $pythonCommand.Path }
    if ([string]::IsNullOrWhiteSpace($pythonPath)) { $pythonPath = "python" }
}

Write-Host "Checking Docker Desktop..."
$null = Invoke-NativeChecked -FilePath $dockerPath -Arguments @("info", "--format", "{{.ServerVersion}}") -CaptureOutput

Write-Host "Checking PyMuPDF in: $pythonPath"
$fitzAvailable = $true
try {
    $null = Invoke-NativeChecked -FilePath $pythonPath -Arguments @("-c", "import fitz; print(fitz.__doc__.splitlines()[0] if fitz.__doc__ else 'PyMuPDF ready')") -CaptureOutput
}
catch {
    $fitzAvailable = $false
}

if (-not $fitzAvailable) {
    Write-Host "PyMuPDF is missing from the selected Python environment; installing it..." -ForegroundColor Yellow
    Invoke-NativeChecked -FilePath $pythonPath -Arguments @("-m", "pip", "install", "--disable-pip-version-check", "PyMuPDF>=1.24,<2")
    $null = Invoke-NativeChecked -FilePath $pythonPath -Arguments @("-c", "import fitz; print('PyMuPDF ready')") -CaptureOutput
}

$grades = if ($ClassNo -eq 0) { @(6..12) } else { @($ClassNo) }
$languages = if ($Language -eq "both") { @("hindi", "english") } else { @($Language) }
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("quantaedge-textbooks-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null
$summary = [System.Collections.Generic.List[object]]::new()
$runStatus = "IN_PROGRESS"
$runError = $null

try {
    foreach ($grade in $grades) {
        foreach ($medium in $languages) {
            $image = "ghcr.io/$($ImageOwner)/quantaedge-textbooks-class-$($grade)-$($medium):latest"
            $stageRoot = Join-Path $tempRoot "class-$grade-$medium"
            $stageBooks = Join-Path $stageRoot "books"
            New-Item -ItemType Directory -Path $stageBooks -Force | Out-Null

            Write-Host ""
            Write-Host "==> Pulling Class $grade ($medium) from $image" -ForegroundColor Cyan
            try {
                Invoke-NativeChecked -FilePath $dockerPath -Arguments @("pull", $image)
            }
            catch {
                throw "Could not pull $image. Check Docker login to ghcr.io and confirm the account has read:packages access. Details: $($_.Exception.Message)"
            }

            $containerId = $null
            try {
                $containerId = Invoke-NativeChecked -FilePath $dockerPath -Arguments @("create", $image, "/__quantaedge_cache_inspection_only") -CaptureOutput
                $containerId = $containerId.Trim()
                if ($containerId -notmatch "^[0-9a-f]{12,64}$") {
                    throw "Docker returned an invalid container ID for $image."
                }

                Invoke-NativeChecked -FilePath $dockerPath -Arguments @("cp", "$($containerId):/index.json", (Join-Path $stageRoot "index.json"))
                Invoke-NativeChecked -FilePath $dockerPath -Arguments @("cp", "$($containerId):/books/.", $stageBooks)
            }
            finally {
                if (-not [string]::IsNullOrWhiteSpace($containerId)) {
                    try {
                        $null = Invoke-NativeChecked -FilePath $dockerPath -Arguments @("rm", "--force", $containerId) -CaptureOutput
                    }
                    catch {
                        Write-Warning "Could not remove temporary Docker container $containerId. Run 'docker container prune' later if needed."
                    }
                }
            }

            $stageIndex = Join-Path $stageRoot "index.json"
            Write-Host "==> Verifying indexed PDFs, SHA-256 hashes and page counts..."
            Invoke-NativeChecked -FilePath $pythonPath -Arguments @(
                $ValidatorPath,
                "--index", $stageIndex,
                "--books-dir", $stageBooks,
                "--image", $image
            )

            $indexData = Get-Content -LiteralPath $stageIndex -Raw -Encoding UTF8 | ConvertFrom-Json
            $destination = Join-Path $OutputRoot "class-$grade\$medium"
            $destinationBooks = Join-Path $destination "books"
            New-Item -ItemType Directory -Path $destinationBooks -Force | Out-Null
            $downloaded = 0
            $reused = 0

            foreach ($book in @($indexData.books)) {
                $bookId = [string]$book.book_id
                $relativeFile = [string]$book.file
                if ($bookId -notmatch "^[A-Za-z0-9][A-Za-z0-9._-]{0,239}$" -or $relativeFile -ne "books/$bookId.pdf") {
                    throw "Refusing unsafe book path in $image index.json."
                }

                $sourcePdf = Join-Path $stageBooks "$bookId.pdf"
                $targetPdf = Join-Path $destinationBooks "$bookId.pdf"
                $expectedHash = ([string]$book.sha256).ToLowerInvariant()
                $targetHash = $null
                if (Test-Path -LiteralPath $targetPdf -PathType Leaf) {
                    $targetHash = (Get-FileHash -LiteralPath $targetPdf -Algorithm SHA256).Hash.ToLowerInvariant()
                }
                if ($targetHash -eq $expectedHash) {
                    $reused++
                    continue
                }

                $targetTemporary = "$targetPdf.download"
                Copy-Item -LiteralPath $sourcePdf -Destination $targetTemporary -Force
                Move-Item -LiteralPath $targetTemporary -Destination $targetPdf -Force
                $downloaded++
            }

            # Publish the index only after every referenced PDF has passed validation/copy.
            $indexTemporary = Join-Path $destination "index.json.download"
            Copy-Item -LiteralPath $stageIndex -Destination $indexTemporary -Force
            Move-Item -LiteralPath $indexTemporary -Destination (Join-Path $destination "index.json") -Force

            $summary.Add([pscustomobject]@{
                class = $grade
                language = $medium
                image = $image
                books = @($indexData.books).Count
                downloaded_or_updated = $downloaded
                reused_verified = $reused
                output_directory = $destination
            })
            Write-Host "Verified Class $grade ($medium): $(@($indexData.books).Count) books; $downloaded downloaded/updated; $reused reused." -ForegroundColor Green
        }
    }

    $runStatus = "COMPLETED"
}
catch {
    $runStatus = "FAILED"
    $runError = $_.Exception.Message
    throw
}
finally {
    $report = [ordered]@{
        schema_version = 1
        status = $runStatus
        downloaded_at_utc = (Get-Date).ToUniversalTime().ToString("o")
        source_repository = "Manav326/QuantaEdge"
        source_registry = "ghcr.io/$ImageOwner/quantaedge-textbooks-class-{6..12}-{hindi|english}:latest"
        output_root = $OutputRoot
        classes = $grades
        languages = $languages
        registries = @($summary)
        error = $runError
    }
    $reportPath = Join-Path $OutputRoot "download-report.json"
    $report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $reportPath -Encoding UTF8
    Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
}

if ($runStatus -eq "COMPLETED") {
    Write-Host ""
    Write-Host "Textbook download completed successfully." -ForegroundColor Green
    Write-Host "Output: $OutputRoot"
    Write-Host "Report: $reportPath"
    Write-Host "The original GHCR PDFs remain unchanged; no textbook binaries were added to Git."
}
