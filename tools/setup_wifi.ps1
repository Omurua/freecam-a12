# Moves the camera from its setup AP onto your home Wi-Fi, without the vendor app.
#
#   1. joins the camera AP and saves its credentials (discovery)
#   2. shows which networks the camera can see, asks for confirmation
#   3. sends WifiSet with your home SSID (passphrase typed by you, hidden, never stored)
#   4. returns the PC to the home Wi-Fi, finds the camera there and grabs a snapshot
#
# Needs a local checkout of https://github.com/zkiiito/A9 and $env:A9_PREKEY.
# Example:
#   $env:A9_PREKEY = '...'
#   .\tools\setup_wifi.ps1 -CamSsid LLM_HA10_123456 -HomeSsid MyWifi -Client C:\src\A9
param(
    [Parameter(Mandatory)] [string]$CamSsid,
    [Parameter(Mandatory)] [string]$HomeSsid,
    [Parameter(Mandatory)] [string]$Client,
    [string]$CamPass = '12345678',
    [string]$CamIp = '192.168.9.252',
    [string]$Out
)
if (-not $env:A9_PREKEY) { throw 'Set $env:A9_PREKEY first' }
# $PSScriptRoot is empty inside param() defaults on Windows PowerShell 5.1
if (-not $Out) { $Out = Join-Path (Split-Path -Parent $PSScriptRoot) 'captures\setup' }
$Wifi = Join-Path $PSScriptRoot 'a12_wifi.py'
New-Item -ItemType Directory -Force $Out | Out-Null
$cfg = Join-Path $Out 'a9_camera.json'
$log = Join-Path $Out 'setup.log'
function Log($m) { "[$(Get-Date -Format HH:mm:ss)] $m" | Tee-Object -FilePath $log -Append }

function Join-CamAp {
    $xml = @"
<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
  <name>$CamSsid</name>
  <SSIDConfig><SSID><name>$CamSsid</name></SSID></SSIDConfig>
  <connectionType>ESS</connectionType>
  <connectionMode>manual</connectionMode>
  <MSM><security>
    <authEncryption><authentication>WPA2PSK</authentication><encryption>AES</encryption><useOneX>false</useOneX></authEncryption>
    <sharedKey><keyType>passPhrase</keyType><protected>false</protected><keyMaterial>$CamPass</keyMaterial></sharedKey>
  </security></MSM>
</WLANProfile>
"@
    $xf = Join-Path $Out 'cam-profile.xml'
    $xml | Out-File -Encoding utf8 $xf
    netsh wlan add profile filename="$xf" user=current | Out-Null
    Remove-Item $xf
    netsh wlan connect name="$CamSsid" ssid="$CamSsid" | Out-Null
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep 1
        $ip = (Get-NetIPAddress -InterfaceAlias 'Wi-Fi' -AddressFamily IPv4 -ErrorAction SilentlyContinue).IPAddress
        if ($ip -like '192.168.9.*') { Log "Joined camera AP as $ip"; return }
    }
    throw 'Could not join camera AP (is the LED blinking and the LLM_ network visible?)'
}

$sent = $false
try {
    Join-CamAp
    Log '--- discovery ---'
    Log (& python "$Client\a9_discover.py" $CamIp --wait 4 --save-config $cfg 2>&1 | Out-String)
    Start-Sleep 8
    Log '--- networks the camera can see ---'
    Log (& python $Wifi --client $Client --config $cfg --scan 2>&1 | Out-String)
    Start-Sleep 8
    Log '--- stored station SSID ---'
    Log (& python $Wifi --client $Client --config $cfg --show 2>&1 | Out-String)
    Start-Sleep 8

    $answer = Read-Host "Send '$HomeSsid' to the camera? It will leave AP mode (s/n)"
    if ($answer -match '^[sSyY]') {
        # Interactive on purpose: a12_wifi.py asks for the passphrase itself, hidden.
        & python $Wifi --client $Client --config $cfg --ssid $HomeSsid
        $sent = ($LASTEXITCODE -eq 0)
        Log "WifiSet sent: $sent"
    } else {
        Log 'Skipped WifiSet'
    }
}
catch { Log "ERROR: $_" }
finally {
    netsh wlan connect name="$HomeSsid" ssid="$HomeSsid" | Out-Null
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep 1
        if (Test-Connection 1.1.1.1 -Count 1 -Quiet) { break }
    }
    Log "Back on home Wi-Fi: $((Get-NetIPAddress -InterfaceAlias 'Wi-Fi' -AddressFamily IPv4).IPAddress)"
}

if ($sent) {
    # UDP broadcast discovery does not get an answer on the home LAN, so find the camera by its Beken MAC
    # instead: ping-sweep the /24 to fill the ARP table, then look for c8:47:8c.
    Log 'Waiting for the camera to join the home network...'
    $found = $false
    $home = (Get-NetIPAddress -InterfaceAlias 'Wi-Fi' -AddressFamily IPv4).IPAddress
    $prefix = $home -replace '\.\d+$', ''
    for ($round = 0; $round -lt 6 -and -not $found; $round++) {
        Start-Sleep 10
        $pings = 1..254 | ForEach-Object { (New-Object System.Net.NetworkInformation.Ping).SendPingAsync("$prefix.$_", 500) }
        try { [Threading.Tasks.Task]::WaitAll($pings) } catch { }
        $n = Get-NetNeighbor -AddressFamily IPv4 -InterfaceAlias 'Wi-Fi' -ErrorAction SilentlyContinue |
             Where-Object { $_.LinkLayerAddress -like 'C8-47-8C*' -and $_.State -ne 'Unreachable' } | Select-Object -First 1
        if ($n) {
            $found = $true
            Log "Camera found on the LAN: $($n.IPAddress) (MAC $($n.LinkLayerAddress))"
            $j = Get-Content $cfg -Raw | ConvertFrom-Json
            $j.ip = $n.IPAddress
            $j | ConvertTo-Json -Compress | Out-File -Encoding ascii $cfg
        }
    }
    if (-not $found) {
        Log 'Camera not found on the LAN yet. Check your router for a client with MAC c8:47:8c:...'
        Log 'If it never shows up, hold MODE ~15 s or power-cycle it repeatedly to get the LLM_ AP back.'
    } else {
        Start-Sleep 8
        Log '--- snapshot over the home LAN ---'
        Log (& python "$Client\a9_live_snapshot.py" --config $cfg -o (Join-Path $Out 'snapshot_lan.jpg') --timeout 10 2>&1 | Out-String)
    }
}
