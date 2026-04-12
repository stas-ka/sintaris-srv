# deploy_taristation2.ps1 — Deploy Copilot Bridge to TariStation2 from Windows.
# Run from sintaris-srv\copilot-bridge directory, or from sintaris-openclaw.
# Reads credentials from sintaris-openclaw\.env automatically.
#
# Usage:  .\deploy\deploy_taristation2.ps1 [-GhToken <token>]

param(
    [string]$GhToken = ""
)

$ErrorActionPreference = "Stop"

$BridgeDir  = Split-Path $PSScriptRoot -Parent
$EnvFile    = Resolve-Path (Join-Path $BridgeDir "..\..\sintaris-openclaw\.env") -ErrorAction SilentlyContinue

# ── Load credentials ──────────────────────────────────────────────────────────
$creds = @{}
if ($EnvFile -and (Test-Path $EnvFile)) {
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match '^\s*([A-Z_]+)\s*=\s*(.+)$') {
            $creds[$Matches[1]] = $Matches[2].Trim()
        }
    }
}

$TargetIP   = $creds["ENG_TARGETHOST_IP"] ?? "192.168.178.27"
$TargetUser = $creds["ENG_HOSTUSER"]      ?? "stas"
$TargetPwd  = $creds["ENG_HOSTPWD"]       ?? "buerger"
$TargetKey  = $creds["ENG_HOSTKEY"]       ?? "SHA256:2Psz9uCmafYyM25q7XAjmdwIV1YhBzX6KfSzn/zqmhE"
$RemoteDir  = "/home/$TargetUser/copilot-bridge"

# ── GitHub token ──────────────────────────────────────────────────────────────
if (-not $GhToken) {
    try { $GhToken = (gh auth token 2>$null).Trim() } catch { }
}

$PlinkArgs = @("-pw", $TargetPwd, "-hostkey", $TargetKey, "-batch", "$TargetUser@$TargetIP")
$PscpArgs  = @("-pw", $TargetPwd, "-hostkey", $TargetKey)

function Invoke-SSH([string]$Cmd) {
    plink @PlinkArgs $Cmd
}

function Send-File([string]$Local, [string]$RemotePath) {
    pscp @PscpArgs $Local "${TargetUser}@${TargetIP}:${RemotePath}"
}

Write-Host "=== Deploying Copilot Bridge → $TargetUser@$TargetIP`:$RemoteDir ===" -ForegroundColor Cyan

# ── Create remote directories ─────────────────────────────────────────────────
Invoke-SSH "mkdir -p $RemoteDir/src $RemoteDir/deploy $RemoteDir/scripts $RemoteDir/doc"

# ── Upload source files ───────────────────────────────────────────────────────
Write-Host "[1/4] Uploading source files..." -ForegroundColor Yellow
Send-File "$BridgeDir\src\server.py"         "$RemoteDir/src/"
Send-File "$BridgeDir\src\copilot_client.py" "$RemoteDir/src/"
Send-File "$BridgeDir\src\config.py"         "$RemoteDir/src/"

Write-Host "[2/4] Uploading config and scripts..." -ForegroundColor Yellow
Send-File "$BridgeDir\requirements.txt"                  "$RemoteDir/"
Send-File "$BridgeDir\.env.example"                      "$RemoteDir/"
Send-File "$BridgeDir\scripts\start.sh"                  "$RemoteDir/scripts/"
Send-File "$BridgeDir\deploy\copilot-bridge.service"     "$RemoteDir/deploy/"
Send-File "$BridgeDir\deploy\install.sh"                 "$RemoteDir/deploy/"
if (Test-Path "$BridgeDir\doc\architecture.md") {
    Send-File "$BridgeDir\doc\architecture.md" "$RemoteDir/doc/"
    Send-File "$BridgeDir\doc\deployment.md"   "$RemoteDir/doc/"
}

# ── Write GH_TOKEN into remote .env ──────────────────────────────────────────
Write-Host "[3/4] Configuring .env on remote..." -ForegroundColor Yellow
if ($GhToken) {
    Invoke-SSH @"
if [ ! -f $RemoteDir/.env ]; then cp $RemoteDir/.env.example $RemoteDir/.env; fi
if grep -q '^GH_TOKEN=' $RemoteDir/.env; then
    sed -i 's|^GH_TOKEN=.*|GH_TOKEN=$GhToken|' $RemoteDir/.env
else
    echo 'GH_TOKEN=$GhToken' >> $RemoteDir/.env
fi
grep -q '^COPILOT_BRIDGE_HOST=' $RemoteDir/.env || echo 'COPILOT_BRIDGE_HOST=127.0.0.1' >> $RemoteDir/.env
"@
    Write-Host "    GH_TOKEN written to remote .env" -ForegroundColor Green
} else {
    Write-Host "    WARNING: No GH_TOKEN found. Set it manually in $RemoteDir/.env on target." -ForegroundColor Red
}

# ── Run install.sh on remote ──────────────────────────────────────────────────
Write-Host "[4/4] Running install.sh on remote..." -ForegroundColor Yellow
Invoke-SSH "chmod +x $RemoteDir/deploy/install.sh $RemoteDir/scripts/start.sh && bash $RemoteDir/deploy/install.sh"

Write-Host ""
Write-Host "=== Deployment complete ===" -ForegroundColor Green
Write-Host "Verify with: plink -pw '$TargetPwd' -hostkey '$TargetKey' -batch $TargetUser@$TargetIP 'curl -s http://127.0.0.1:8765/health'"
