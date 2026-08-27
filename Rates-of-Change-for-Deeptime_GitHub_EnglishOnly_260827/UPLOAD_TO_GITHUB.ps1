$ErrorActionPreference = "Stop"

$repositoryUrl = "https://github.com/CUGB-zhaohy/Rates-of-Change-for-Deeptime.git"
$packageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$timeStamp = Get-Date -Format "yyyyMMdd_HHmmss"
$uploadRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("RoC_GitHub_upload_" + $timeStamp)

function Find-GitExecutable {
    $command = Get-Command git.exe -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }

    $programFilesGit = "C:\Program Files\Git\cmd\git.exe"
    if (Test-Path -LiteralPath $programFilesGit) { return $programFilesGit }

    $desktopRoot = Join-Path $env:LOCALAPPDATA "GitHubDesktop"
    $desktopCandidates = Get-ChildItem -Path (Join-Path $desktopRoot "app-*") -Directory -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending |
        ForEach-Object { Join-Path $_.FullName "resources\app\git\cmd\git.exe" }
    foreach ($candidate in $desktopCandidates) {
        if (Test-Path -LiteralPath $candidate) { return $candidate }
    }

    throw "Git was not found. Install Git for Windows or GitHub Desktop, then run this file again."
}

$git = Find-GitExecutable
Write-Host "1/5 Downloading the current GitHub repository..." -ForegroundColor Cyan
& $git clone $repositoryUrl $uploadRoot
if ($LASTEXITCODE -ne 0) {
    throw "Clone failed. Check the network connection and complete GitHub authorization if prompted."
}

Write-Host "2/5 Merging the software, documentation, and manuscript results..." -ForegroundColor Cyan
$arguments = @(
    $packageRoot,
    $uploadRoot,
    "/E",
    "/R:2",
    "/W:2",
    "/NFL",
    "/NDL",
    "/NJH",
    "/NJS",
    "/NP",
    "/XD",
    (Join-Path $packageRoot ".git")
)
& robocopy @arguments | Out-Null
if ($LASTEXITCODE -ge 8) {
    throw "File copy failed. Robocopy exit code: $LASTEXITCODE"
}

Write-Host "Removing obsolete non-English repository files..." -ForegroundColor Cyan
$cjkNamePattern = "[\u3400-\u9FFF]"
$nonEnglishNames = Get-ChildItem -LiteralPath $uploadRoot -Recurse -Force |
    Where-Object { $_.Name -match $cjkNamePattern } |
    Sort-Object { $_.FullName.Length } -Descending
foreach ($item in $nonEnglishNames) {
    Remove-Item -LiteralPath $item.FullName -Recurse -Force
}
$obsoleteReadme = Join-Path $uploadRoot "README_zh-CN.md"
if (Test-Path -LiteralPath $obsoleteReadme) {
    Remove-Item -LiteralPath $obsoleteReadme -Force
}

$textExtensions = @(
    ".bat", ".cff", ".command", ".csv", ".md", ".ps1", ".py",
    ".svg", ".txt", ".yaml", ".yml"
)
$nonEnglishTextFiles = Get-ChildItem -LiteralPath $uploadRoot -Recurse -File |
    Where-Object { $textExtensions -contains $_.Extension.ToLowerInvariant() } |
    Where-Object {
        try {
            [System.IO.File]::ReadAllText($_.FullName) -match $cjkNamePattern
        }
        catch {
            $false
        }
    }
foreach ($item in $nonEnglishTextFiles) {
    Remove-Item -LiteralPath $item.FullName -Force
}

Write-Host "3/5 Creating the Git commit..." -ForegroundColor Cyan
& $git -C $uploadRoot config user.name "CUGB-zhaohy"
if ($LASTEXITCODE -ne 0) { throw "Could not configure the Git user name." }
& $git -C $uploadRoot config user.email "CUGB-zhaohy@users.noreply.github.com"
if ($LASTEXITCODE -ne 0) { throw "Could not configure the Git user email." }
& $git -C $uploadRoot add --all
if ($LASTEXITCODE -ne 0) { throw "Git could not stage the files." }

& $git -C $uploadRoot diff --cached --quiet
$diffExitCode = $LASTEXITCODE
if ($diffExitCode -eq 0) {
    Write-Host "The online repository already contains the same files. Nothing needs to be uploaded." -ForegroundColor Green
    exit 0
}
if ($diffExitCode -ne 1) {
    throw "Git could not inspect the staged changes. Exit code: $diffExitCode"
}

& $git -C $uploadRoot commit -m "Add software workflow and manuscript result archive"
if ($LASTEXITCODE -ne 0) { throw "Git commit failed." }

Write-Host "4/5 Uploading to the main branch..." -ForegroundColor Cyan
& $git -C $uploadRoot push origin main
if ($LASTEXITCODE -ne 0) {
    throw "Upload failed. Check the GitHub login status and repository permissions."
}

Write-Host "5/5 Upload completed successfully." -ForegroundColor Green
Write-Host "Repository: https://github.com/CUGB-zhaohy/Rates-of-Change-for-Deeptime"
Write-Host "Temporary working copy: $uploadRoot"
