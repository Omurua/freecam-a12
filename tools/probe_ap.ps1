# Joins the camera's setup AP, probes it and grabs a snapshot, then ALWAYS returns to the home Wi-Fi.
# Useful when the PC's only internet connection is Wi-Fi.
#
# Needs a local checkout of https://github.com/zkiiito/A9 and the shared PPRPC prekey in $env:A9_PREKEY
# (documented in the public analyses linked from that repo, never commit it here).
#
# Example:
#   $env:A9_PREKEY = '...'
#   .\tools\probe_ap.ps1 -CamSsid LLM_HA10_123456 -HomeSsid MyWifi -Client C:\src\A9
param(
    [Parameter(Mandatory)] [string]$CamSsid,
    [Parameter(Mandatory)] [string]$HomeSsid,
    [Parameter(Mandatory)] [string]$Client,
    [string]$CamPass = '12345678',
    [string]$CamIp = '192.168.9.252',
    [string]$Out = (Join-Path (Get-Location) 'captures\probe')
)
if (-not $env:A9_PREKEY) { throw 'Set $env:A9_PREKEY first' }
New-Item -ItemType Directory -Force $Out | Out-Null
$log = Join-Path $Out 'probe.log'
function Log($m) { "[$(Get-Date -Format HH:mm:ss)] $m" | Tee-Object -FilePath $log -Append }

try {
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
    Log (netsh wlan add profile filename="$xf" user=current | Out-String)
    Remove-Item $xf
    Log (netsh wlan connect name="$CamSsid" ssid="$CamSsid" | Out-String)

    $ok = $false
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep 1
        $ip = (Get-NetIPAddress -InterfaceAlias 'Wi-Fi' -AddressFamily IPv4 -ErrorAction SilentlyContinue).IPAddress
        if ($ip -like '192.168.9.*') { $ok = $true; break }
    }
    Log "Wi-Fi IP: $ip (joined=$ok)"
    if (-not $ok) { throw 'Could not join camera AP' }
    Log (ping -n 3 $CamIp | Out-String)

    foreach ($p in 21,22,23,80,443,554,1935,6123,6668,7000,8000,8080,8554,9000,20190,20191,32108) {
        $c = New-Object System.Net.Sockets.TcpClient
        $t = $c.ConnectAsync($CamIp, $p)
        if ($t.Wait(800) -and $c.Connected) { Log "TCP $p OPEN" }
        $c.Dispose()
    }

    $cfg = Join-Path $Out 'a9_camera.json'
    Log '--- a9_discover ---'
    Log (& python "$Client\a9_discover.py" $CamIp --wait 4 --save-config $cfg 2>&1 | Out-String)
    Log '--- a9_live_snapshot ---'
    Log (& python "$Client\a9_live_snapshot.py" $CamIp --config $cfg -o (Join-Path $Out 'snapshot.jpg') --timeout 10 2>&1 | Out-String)
}
catch { Log "ERROR: $_" }
finally {
    Log (netsh wlan connect name="$HomeSsid" ssid="$HomeSsid" | Out-String)
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep 1
        if (Test-Connection 1.1.1.1 -Count 1 -Quiet) { break }
    }
    Log "Back on home Wi-Fi: $((Get-NetIPAddress -InterfaceAlias 'Wi-Fi' -AddressFamily IPv4).IPAddress)"
}
