# Captures everything the camera sends to the internet, by making the PC its router for a while.
#
#   1. starts Windows Mobile Hotspot with a temporary SSID and a random passphrase
#   2. tells the camera (over the LAN) to join that hotspot (WifiSet)
#   3. captures all its traffic for -Minutes, without opening any stream (idle behaviour)
#   4. sends the camera back to the home Wi-Fi (asks for its passphrase, hidden), restores the hotspot settings
#
# Capture backends:
#   default     pktmon (built into Windows, needs an ELEVATED PowerShell). Only records the camera's outgoing packets.
#   -Wireshark  dumpcap from Wireshark + Npcap. Records BOTH directions, filtered by the camera's MAC; no admin needed.
# -Reboot asks you to power-cycle the camera right after the capture starts, to record its start-up traffic
# (server lookup, firmware checks).
# -AppPairing (needs -Wireshark and -CamMac) shows the hotspot's SSID and passphrase and starts capturing at once, so
# the vendor app can put the camera on the hotspot itself. The passphrase is only shown on screen, never logged.
#
# Stop any running video server first: the camera only accepts one session at a time. Needs a zkiiito/A9 checkout,
# $env:A9_PREKEY and a9_camera.json with the camera's current LAN IP.
#
# Example:
#   $env:A9_PREKEY = '...'
#   .\tools\capture_hotspot.ps1 -HomeSsid MyWifi -Client C:\src\A9 -Minutes 10 -Wireshark -Reboot
param(
    [Parameter(Mandatory)] [string]$HomeSsid,
    [Parameter(Mandatory)] [string]$Client,
    [int]$Minutes = 10,
    [string]$Config,
    [string]$Out,
    [switch]$Wireshark,
    [switch]$Reboot,
    [switch]$AppPairing,
    [string]$CamMac,
    [string]$Dumpcap = 'C:\Program Files\Wireshark\dumpcap.exe'
)
if (-not $env:A9_PREKEY) { throw 'Set $env:A9_PREKEY first' }
if ($AppPairing -and (-not $Wireshark -or -not $CamMac)) { throw '-AppPairing needs -Wireshark and -CamMac' }
if ($Wireshark) {
    if (-not (Test-Path $Dumpcap)) { throw "dumpcap not found at $Dumpcap (install Wireshark with Npcap, or pass -Dumpcap)" }
} elseif (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Run this from an elevated PowerShell (pktmon needs admin), or use -Wireshark' }
$Root = Split-Path -Parent $PSScriptRoot
if (-not $Config) { $Config = Join-Path $Root 'captures\setup\a9_camera.json' }
if (-not $Out) { $Out = Join-Path $Root ("captures\traffic-" + (Get-Date -Format 'yyyyMMdd-HHmm')) }
$Wifi = Join-Path $PSScriptRoot 'a12_wifi.py'
New-Item -ItemType Directory -Force $Out | Out-Null
$log = Join-Path $Out 'capture.log'
function Log($m) { "[$(Get-Date -Format HH:mm:ss)] $m" | Tee-Object -FilePath $log -Append }

# ---------- Mobile Hotspot (WinRT) ----------
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Networking.Connectivity.NetworkInformation, Windows.Networking.Connectivity, ContentType = WindowsRuntime]
$null = [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager, Windows.Networking.NetworkOperators, ContentType = WindowsRuntime]
$asTaskGeneric = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' } |
    Select-Object -First 1
$asTaskAction = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncAction' } |
    Select-Object -First 1
function Await($op, [Type]$type) { $t = $asTaskGeneric.MakeGenericMethod($type).Invoke($null, @($op)); $t.Wait(-1) | Out-Null; $t.Result }
function AwaitAction($op) { $t = $asTaskAction.Invoke($null, @($op)); $t.Wait(-1) | Out-Null }

$profile = [Windows.Networking.Connectivity.NetworkInformation]::GetInternetConnectionProfile()
$tm = [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager]::CreateFromConnectionProfile($profile)
$orig = $tm.GetCurrentAccessPointConfiguration()
$origSsid, $origPass = $orig.Ssid, $orig.Passphrase

function Set-CamIp($ip) {
    $j = Get-Content $Config -Raw | ConvertFrom-Json
    $j.ip = $ip
    $j | ConvertTo-Json -Compress | Out-File -Encoding ascii $Config
}

function Find-Cam([string]$prefix, [int]$tries) {
    for ($i = 0; $i -lt $tries; $i++) {
        Start-Sleep 5
        $pings = 1..254 | ForEach-Object { (New-Object System.Net.NetworkInformation.Ping).SendPingAsync("$prefix.$_", 400) }
        try { [Threading.Tasks.Task]::WaitAll($pings) } catch { }
        $n = Get-NetNeighbor -AddressFamily IPv4 -ErrorAction SilentlyContinue |
             Where-Object { $_.LinkLayerAddress -like 'C8-47-8C*' -and $_.IPAddress -like "$prefix.*" -and $_.State -ne 'Unreachable' } |
             Select-Object -First 1
        if ($n) { return $n.IPAddress }
    }
    return $null
}

$labSsid = 'freecam-lab'
if ($AppPairing) {
    # short and lowercase: it has to be typed on the phone
    $env:FREECAM_LAB_PASS = -join ((48..57) + (97..122) | Get-Random -Count 10 | ForEach-Object { [char]$_ })
} else {
    $env:FREECAM_LAB_PASS = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 16 | ForEach-Object { [char]$_ })
}
$camLanIp = (Get-Content $Config -Raw | ConvertFrom-Json).ip
$pktmonOn = $false
$hotspotOn = $false
try {
    # 1. hotspot
    $cfg = $tm.GetCurrentAccessPointConfiguration()
    $cfg.Ssid = $labSsid
    $cfg.Passphrase = $env:FREECAM_LAB_PASS
    AwaitAction ($tm.ConfigureAccessPointAsync($cfg))
    $r = Await ($tm.StartTetheringAsync()) ([Windows.Networking.NetworkOperators.NetworkOperatorTetheringOperationResult])
    Log "Hotspot start: $($r.Status) $($r.AdditionalErrorMessage)"
    if ($r.Status -ne 'Success') { throw 'Could not start the Mobile Hotspot' }
    $hotspotOn = $true
    Start-Sleep 3
    $hsIp = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object IPAddress -like '192.168.137.*' | Select-Object -First 1).IPAddress
    Log "Hotspot '$labSsid' up, PC side $hsIp"

    # 2. move the camera onto the hotspot
    if ($AppPairing) {
        Write-Host ''
        Write-Host ">>> In the app, use Wi-Fi '$labSsid' with passphrase: $env:FREECAM_LAB_PASS <<<"
        Write-Host ''
    } else {
        Log "Sending '$labSsid' to the camera at $camLanIp"
        Log (& python $Wifi --client $Client --ip $camLanIp --config $Config --ssid $labSsid --password-env FREECAM_LAB_PASS 2>&1 | Out-String)
        $camIp = Find-Cam '192.168.137' 24
        if (-not $camIp) { throw 'Camera did not show up on the hotspot within 2 minutes' }
        Log "Camera joined the hotspot as $camIp"
    }

    # 3. capture on the hotspot's virtual adapter, before NAT
    $pcap = Join-Path $Out 'camera.pcapng'
    if ($Wireshark) {
        if ($CamMac) { $camMac = $CamMac.Replace('-', ':').ToLower() }
        else { $camMac = (Get-NetNeighbor -IPAddress $camIp -AddressFamily IPv4).LinkLayerAddress.Replace('-', ':').ToLower() }
        $hsAdapter = Get-NetIPAddress -AddressFamily IPv4 -IPAddress $hsIp | Get-NetAdapter
        $iface = "\Device\NPF_$($hsAdapter.InterfaceGuid)"
        Log "dumpcap on $($hsAdapter.Name) ($iface), filter: ether host $camMac"
        # Windows PowerShell joins -ArgumentList with spaces and does not quote, so quote by hand
        $dump = Start-Process -FilePath $Dumpcap -NoNewWindow -PassThru -ArgumentList (
            "-i `"$iface`" -f `"ether host $camMac`" -w `"$pcap`" -a duration:$($Minutes * 60) -q")
        Start-Sleep 2
        if ($dump.HasExited) { throw "dumpcap exited immediately (code $($dump.ExitCode)), nothing captured" }
    } else {
        $etl = Join-Path $Out 'camera.etl'
        pktmon filter remove | Out-Null
        pktmon filter add Camera -i $camIp | Out-Null
        pktmon start --capture --pkt-size 0 --file-name $etl | Out-Null
        $pktmonOn = $true
    }
    Log "Capturing for $Minutes minutes... (do not open the video stream, this records idle behaviour)"
    if ($Reboot) {
        Start-Sleep 5
        Write-Host ''
        Write-Host '>>> NOW: unplug the camera, wait 5 seconds and plug it back in. <<<'
        Write-Host ''
        Log 'Asked for a camera power cycle'
    }
    if ($Wireshark) {
        $dump.WaitForExit()
        if (-not (Test-Path $pcap)) { throw "dumpcap finished (code $($dump.ExitCode)) without writing $pcap" }
    } else {
        Start-Sleep -Seconds ($Minutes * 60)
        pktmon stop | Out-Null
        $pktmonOn = $false
        pktmon etl2pcap $etl --out $pcap | Out-Null
    }
    Log "Saved $pcap"
    if ($AppPairing) {
        $camIp = Find-Cam '192.168.137' 12
        if (-not $camIp) { throw 'Camera is not on the hotspot. To reconfigure it, hold its button 5 s for pairing mode.' }
        # binding can change the camera's secret, so read it again instead of trusting the saved config
        Log (& python "$Client\a9_discover.py" $camIp --wait 4 --save-config $Config 2>&1 | Out-String)
    }
    if ($Reboot) {
        # after a reboot the camera may have taken a different address on the hotspot
        $again = Find-Cam '192.168.137' 6
        if ($again) { $camIp = $again }
    }

    # 4. back to the home Wi-Fi (interactive, hidden passphrase)
    Set-CamIp $camIp
    Start-Sleep 8
    Write-Host "Now the camera goes back to '$HomeSsid'. Type that network's passphrase:"
    & python $Wifi --client $Client --ip $camIp --config $Config --ssid $HomeSsid
    Log "WifiSet $HomeSsid exit code: $LASTEXITCODE"
}
catch { Log "ERROR: $_" }
finally {
    if ($pktmonOn) { pktmon stop | Out-Null }
    if (-not $Wireshark) { pktmon filter remove | Out-Null }
    if ($dump -and -not $dump.HasExited) { $dump.Kill() }
    if ($hotspotOn) {
        Start-Sleep 5
        $null = Await ($tm.StopTetheringAsync()) ([Windows.Networking.NetworkOperators.NetworkOperatorTetheringOperationResult])
        Log 'Hotspot stopped'
    }
    $restore = $tm.GetCurrentAccessPointConfiguration()
    $restore.Ssid = $origSsid
    $restore.Passphrase = $origPass
    AwaitAction ($tm.ConfigureAccessPointAsync($restore))
    Remove-Item Env:FREECAM_LAB_PASS -ErrorAction SilentlyContinue
    Log 'Hotspot settings restored'
}

$homeIp = Find-Cam (($camLanIp -replace '\.\d+$', '')) 12
if ($homeIp) { Set-CamIp $homeIp; Log "Camera is back on the home LAN as $homeIp" }
else { Log 'Camera not seen on the home LAN yet. If it never comes back: hold MODE ~15 s or power-cycle it for the LLM_ AP.' }
