# Runs one or more commands on the camera's RT-Thread telnet shell (TCP 20023) and prints the output,
# filtering out the camera's interleaved background logging so command replies are readable.
#
# The camera exposes this root shell over Wi-Fi while in softAP mode (no soldering). Connect the PC to the
# camera's LLM_ AP first, or pass -JoinSsid to let the script switch Wi-Fi and switch back.
#
# This is a READ-ORIENTED helper: it sends exactly the commands you pass. It does not write flash by itself.
# Login is password-only ('123' by default); the shell is RT-Thread finsh ('msh />').
#
# Examples:
#   .\tools\telnet_cam.ps1 -Commands 'help'                 # already on the LLM_ AP
#   .\tools\telnet_cam.ps1 -JoinSsid LLM_HA10_XXXXXX -HomeSsid CodeNet -Commands 'help','fal'
param(
    [string[]]$Commands = @('help'),
    [string]$CamIp = '192.168.9.252',
    [int]$Port = 20023,
    [string]$Password = '123',
    [string]$JoinSsid,
    [string]$HomeSsid,
    [int]$ReplyMs = 2000
)
$noise = '\[xm\]led|jpeg fps:|^date: 20|audio:len|vbat volt|xvideo\.c|->fps=|\[pprpc|\[iot\.dev|pprpc_|iot_dev_|GetServers|xglbs'

function Join-Ap($ssid) {
    netsh wlan connect name="$ssid" ssid="$ssid" | Out-Null
    for ($i = 0; $i -lt 25; $i++) {
        Start-Sleep 1
        if ((Get-NetIPAddress -InterfaceAlias 'Wi-Fi' -AddressFamily IPv4 -ErrorAction SilentlyContinue).IPAddress -like '192.168.9.*') { return $true }
    }
    return $false
}

try {
    if ($JoinSsid) { if (-not (Join-Ap $JoinSsid)) { throw "Could not join $JoinSsid" } }

    $c = New-Object System.Net.Sockets.TcpClient
    $c.Connect($CamIp, $Port)
    $s = $c.GetStream(); $s.ReadTimeout = 1500
    function RX($ms) {
        # Keep reading in short slices for up to $ms, so replies split across packets are not cut off.
        $sb = New-Object Text.StringBuilder; $buf = New-Object byte[] 8192
        $deadline = (Get-Date).AddMilliseconds($ms)
        while ((Get-Date) -lt $deadline) {
            if ($s.DataAvailable) { $n = $s.Read($buf, 0, 8192); [void]$sb.Append([Text.Encoding]::ASCII.GetString($buf, 0, $n)) }
            else { Start-Sleep -Milliseconds 150 }
        }
        $sb.ToString()
    }
    function TX($t) { $b = [Text.Encoding]::ASCII.GetBytes("$t`r`n"); $s.Write($b, 0, $b.Length); $s.Flush() }

    [void](RX 800)                 # banner + pwd>> prompt
    TX $Password; [void](RX 1000)  # log in

    foreach ($cmd in $Commands) {
        TX $cmd
        $out = RX $ReplyMs
        "===== $cmd ====="
        ($out -replace '[^\x20-\x7e\r\n]', '.' -split "`n" | Where-Object { $_ -notmatch $noise -and $_.Trim() }) -join "`n"
        ''
    }
    $c.Close()
}
catch { "ERROR: $_" }
finally {
    if ($HomeSsid) { netsh wlan connect name="$HomeSsid" ssid="$HomeSsid" | Out-Null }
}
