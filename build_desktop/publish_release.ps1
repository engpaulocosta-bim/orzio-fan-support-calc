#Requires -Version 5.1
<#
.SYNOPSIS
  Creates or updates a GitHub release and uploads desktop artifacts.

.DESCRIPTION
  - Detects the GitHub repo from the current git remote
  - Reads a GitHub token from `git credential fill`
  - Creates the release tag if needed via the GitHub Releases API
  - Uploads the portable desktop package and executable

.EXAMPLE
  PowerShell.exe -NoProfile -ExecutionPolicy Bypass -File .\build_desktop\publish_release.ps1
#>
param(
    [string] $Version,
    [string] $Tag,
    [string] $ReleaseName,
    [string] $TargetCommitish = "master",
    [string] $Notes,
    [switch] $Draft,
    [switch] $Prerelease
)

$ErrorActionPreference = "Stop"

function Write-Step([string] $Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Get-VersionFromPyProject([string] $RepoRoot) {
    $pyprojectPath = Join-Path $RepoRoot "pyproject.toml"
    if (-not (Test-Path $pyprojectPath)) {
        throw "pyproject.toml not found at $pyprojectPath"
    }

    $match = Select-String -Path $pyprojectPath -Pattern '^version\s*=\s*"([^"]+)"' | Select-Object -First 1
    if (-not $match) {
        throw "Could not find version in pyproject.toml"
    }

    return $match.Matches[0].Groups[1].Value
}

function Get-RepoSlug([string] $RepoRoot) {
    $remoteUrl = (git -C $RepoRoot remote get-url origin).Trim()
    if ($remoteUrl -match 'github\.com[:/](.+?)(?:\.git)?$') {
        return $Matches[1]
    }

    throw "Origin remote is not a GitHub repository: $remoteUrl"
}

function Get-GitHubToken() {
    $request = "protocol=https`nhost=github.com`n`n"
    $lines = $request | git credential fill
    if ($LASTEXITCODE -ne 0) {
        throw "git credential fill failed with exit code $LASTEXITCODE"
    }

    $values = @{}
    foreach ($line in $lines) {
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }

        $parts = $line -split '=', 2
        if ($parts.Count -eq 2) {
            $values[$parts[0]] = $parts[1]
        }
    }

    if (-not $values.ContainsKey("password") -or [string]::IsNullOrWhiteSpace($values["password"])) {
        throw "No GitHub token returned by git credential fill"
    }

    return $values["password"]
}

function New-GitHubHeaders([string] $Token) {
    return @{
        Authorization         = "Bearer $Token"
        Accept                = "application/vnd.github+json"
        "X-GitHub-Api-Version" = "2022-11-28"
        "User-Agent"          = "sfsc-release-script"
    }
}

function Invoke-GitHubJson(
    [string] $Method,
    [string] $Uri,
    [hashtable] $Headers,
    [object] $Body = $null
) {
    $params = @{
        Method  = $Method
        Uri     = $Uri
        Headers = $Headers
    }

    if ($null -ne $Body) {
        $params.ContentType = "application/json"
        $params.Body = ($Body | ConvertTo-Json -Depth 10)
    }

    return Invoke-RestMethod @params
}

function Get-ReleaseByTag([string] $RepoSlug, [string] $TagName, [hashtable] $Headers) {
    $uri = "https://api.github.com/repos/$RepoSlug/releases/tags/$TagName"
    try {
        return Invoke-GitHubJson -Method "GET" -Uri $uri -Headers $Headers
    } catch {
        $response = $_.Exception.Response
        if ($response -and [int]$response.StatusCode -eq 404) {
            return $null
        }
        throw
    }
}

function New-Release([string] $RepoSlug, [string] $TagName, [string] $ReleaseTitle, [string] $Target, [string] $ReleaseNotes, [bool] $IsDraft, [bool] $IsPrerelease, [hashtable] $Headers) {
    $uri = "https://api.github.com/repos/$RepoSlug/releases"
    $body = @{
        tag_name         = $TagName
        target_commitish = $Target
        name             = $ReleaseTitle
        body             = $ReleaseNotes
        draft            = $IsDraft
        prerelease       = $IsPrerelease
    }

    return Invoke-GitHubJson -Method "POST" -Uri $uri -Headers $Headers -Body $body
}

function Update-Release([string] $RepoSlug, [int] $ReleaseId, [string] $ReleaseTitle, [string] $ReleaseNotes, [bool] $IsDraft, [bool] $IsPrerelease, [hashtable] $Headers) {
    $uri = "https://api.github.com/repos/$RepoSlug/releases/$ReleaseId"
    $body = @{
        name       = $ReleaseTitle
        body       = $ReleaseNotes
        draft      = $IsDraft
        prerelease = $IsPrerelease
    }

    return Invoke-GitHubJson -Method "PATCH" -Uri $uri -Headers $Headers -Body $body
}

function Remove-ReleaseAsset([string] $RepoSlug, [int] $AssetId, [hashtable] $Headers) {
    $uri = "https://api.github.com/repos/$RepoSlug/releases/assets/$AssetId"
    Invoke-GitHubJson -Method "DELETE" -Uri $uri -Headers $Headers | Out-Null
}

function Upload-ReleaseAsset([string] $UploadUrlTemplate, [string] $AssetPath, [hashtable] $Headers) {
    $uploadUrl = $UploadUrlTemplate.Split('{')[0]
    $fileName = [System.IO.Path]::GetFileName($AssetPath)
    $encodedName = [System.Uri]::EscapeDataString($fileName)
    $uri = "{0}?name={1}" -f $uploadUrl, $encodedName

    return Invoke-RestMethod -Method "POST" `
        -Uri $uri `
        -Headers $Headers `
        -InFile $AssetPath `
        -ContentType "application/octet-stream"
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir

if (-not $Version) {
    $Version = Get-VersionFromPyProject -RepoRoot $repoRoot
}

if (-not $Tag) {
    $Tag = "v$Version"
}

if (-not $ReleaseName) {
    $ReleaseName = "SFSC v$Version"
}

if (-not $Notes) {
    $Notes = @"
Portable Windows release for SFSC v$Version.

Recommended download:
- SFSC_v$Version`_Windows_Portable.zip

Alternative:
- SFSC.exe

Usage:
1. Download the ZIP package.
2. Extract it to any folder.
3. Run SFSC.exe.

No installer is required.
"@
}

$assets = @(
    (Join-Path $repoRoot "dist\SFSC_v$Version`_Windows_Portable.zip"),
    (Join-Path $repoRoot "dist\SFSC.exe")
)

foreach ($asset in $assets) {
    if (-not (Test-Path $asset)) {
        throw "Required asset not found: $asset"
    }
}

Write-Step "Resolving repository and credentials"
$repoSlug = Get-RepoSlug -RepoRoot $repoRoot
$token = Get-GitHubToken
$headers = New-GitHubHeaders -Token $token

Write-Step "Checking release $Tag in $repoSlug"
$release = Get-ReleaseByTag -RepoSlug $repoSlug -TagName $Tag -Headers $headers
if (-not $release) {
    Write-Step "Creating release $ReleaseName"
    $release = New-Release -RepoSlug $repoSlug -TagName $Tag -ReleaseTitle $ReleaseName -Target $TargetCommitish -ReleaseNotes $Notes -IsDraft:$Draft.IsPresent -IsPrerelease:$Prerelease.IsPresent -Headers $headers
} else {
    Write-Host "Release already exists: $($release.html_url)" -ForegroundColor Yellow
    Write-Step "Updating release notes"
    $release = Update-Release -RepoSlug $repoSlug -ReleaseId $release.id -ReleaseTitle $ReleaseName -ReleaseNotes $Notes -IsDraft:$Draft.IsPresent -IsPrerelease:$Prerelease.IsPresent -Headers $headers
}

foreach ($assetPath in $assets) {
    $assetName = [System.IO.Path]::GetFileName($assetPath)
    $existing = @($release.assets | Where-Object { $_.name -eq $assetName })
    foreach ($item in $existing) {
        Write-Step "Removing existing asset $assetName"
        Remove-ReleaseAsset -RepoSlug $repoSlug -AssetId $item.id -Headers $headers
    }

    Write-Step "Uploading $assetName"
    Upload-ReleaseAsset -UploadUrlTemplate $release.upload_url -AssetPath $assetPath -Headers $headers | Out-Null
}

foreach ($item in @($release.assets)) {
    $keep = $false
    foreach ($assetPath in $assets) {
        if ($item.name -eq [System.IO.Path]::GetFileName($assetPath)) {
            $keep = $true
            break
        }
    }

    if (-not $keep) {
        Write-Step "Removing old asset $($item.name)"
        Remove-ReleaseAsset -RepoSlug $repoSlug -AssetId $item.id -Headers $headers
    }
}

$release = Get-ReleaseByTag -RepoSlug $repoSlug -TagName $Tag -Headers $headers

Write-Host ""
Write-Host "Release published successfully:" -ForegroundColor Green
Write-Host $release.html_url -ForegroundColor Green
