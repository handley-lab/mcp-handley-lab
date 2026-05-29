param (
    [Parameter(Mandatory=$true)]
    [string]$ScriptPath,

    [Parameter(Mandatory=$false)]
    [string[]]$ScriptArgs = @()
)

# 1. Enforce strict UTF-8 to prevent PowerShell's native UTF-16 corruption
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "[Shell Mechanic] Environment secured: UTF-8 Encoding Locked." -ForegroundColor Cyan

# 2. Safely resolve the Python executable
$PythonBin = $null
$Candidates = @("py", "python", "python3")

foreach ($Cand in $Candidates) {
    if (Get-Command $Cand -ErrorAction SilentlyContinue) {
        $PythonBin = $Cand
        break
    }
}

if ($null -eq $PythonBin) {
    Write-Error "[Shell Mechanic] Fatal Friction: Could not resolve a valid Python executable. 'py', 'python', and 'python3' failed."
    exit 1
}

Write-Host "[Shell Mechanic] Executable resolved: $PythonBin" -ForegroundColor Green

# 3. Formulate and execute
if (!(Test-Path $ScriptPath)) {
    Write-Error "[Shell Mechanic] Target script does not exist: $ScriptPath"
    exit 1
}

Write-Host "[Shell Mechanic] Engaging script: $ScriptPath" -ForegroundColor Cyan

# Execute
if ($ScriptArgs.Count -gt 0) {
    & $PythonBin $ScriptPath $ScriptArgs
} else {
    & $PythonBin $ScriptPath
}

$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
    Write-Host "[Shell Mechanic] Script exited with code $exitCode" -ForegroundColor Red
} else {
    Write-Host "[Shell Mechanic] Execution complete." -ForegroundColor Green
}
exit $exitCode
