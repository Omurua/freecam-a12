# Findings

Lab notes, newest first. Device identifiers (DID, MAC suffix, secrets) are redacted.

## 2026-10-27: on the home Wi-Fi without the app ✅

- [`tools/setup_wifi.ps1`](../tools/setup_wifi.ps1) sent `WifiSet` (2602) with the home SSID; the camera answered
  `code=0` and joined the home network within a minute, from the station MAC predicted by `GetNetworkInfo`.
- **UDP broadcast discovery got no answer on the home LAN** (it did in AP mode). The camera was found instead by
  its Beken MAC prefix in the ARP table; the setup script now does that.
- A snapshot over the home LAN with the saved DID + secret worked: 640×480 JPEG.
- **Continuous video works** over the home LAN with zkiiito's `a9_mjpeg_server.py` (`pip install av numpy`),
  viewed in the browser at `http://127.0.0.1:8080/`.
- ⚠️ **The `LLM_` setup AP still shows up** in Windows' network list more than 5 minutes after the camera
  joined the home network. If confirmed (Windows can cache scan results), the camera keeps its open-password AP
  up while it is on your Wi-Fi, which lets anyone nearby join it and read its secret.

## 2026-10-27: control commands work on the HA10

First attempt with [`tools/a12_wifi.py`](../tools/a12_wifi.py): LanAuth succeeded but `WifiAPGet`, `WifiGet` and
`WifiSet` got **no reply at all**. The camera stayed in AP mode, nothing was stored.

**Cause:** commands were sent right after `SyncConn` (106). Like [cheap-shot](https://github.com/Yeti47/cheap-shot)
does, the client must first let the camera push its own heartbeats (107) and answer them. After adding a ~2 s
pump after 106, every command answered with `code=0`.

`a12_wifi.py --probe` results (all read-only):

| Cmd | Name | Reply |
|---|---|---|
| 2653 | StorageInfo | `{1: 4}` |
| 2603 | WifiGet | empty: no station SSID stored |
| 2601 | WifiAPGet | list of nearby networks, each `{1: ssid, 2: n}`. Takes ~2 s (the camera scans) |
| 2630 | ConfigGet | `{2: 1, 4: 2}` |
| 2632 | TimeGet | `{3: 1514765022}` = 2018-01-01, clock never synced |
| 2634 | LedGet | empty |
| 2636 | IRCutGet | `{1: 2}` = day mode |
| 2649 | FlipGet | `{1: 1}` |
| 2685 | GetNetworkInfo | IPs all `0.0.0.0` in AP mode; field 9 = **station MAC** |
| 2638 | SecretGet | empty |

- The station MAC is the AP BSSID with the lowest bit cleared (`…:55` → `…:54`), the same pattern reported by
  ino-a9-local-bridge. That is the MAC to block or reserve on the router.
- The camera saw a home network on **channel 13** without problems.

## 2026-10-27: first offline snapshot ✅

**Setup:** camera powered over USB, in setup mode (LED blinking, `LLM_HA10_…` AP visible). No Linklemo app,
no account, no internet on the camera side. Probe run with [`tools/probe_ap.ps1`](../tools/probe_ap.ps1) and the
[zkiiito/A9](https://github.com/zkiiito/A9) client.

**Results**

- Joining the AP with `12345678` works; the camera is `192.168.9.252`, the PC gets `192.168.9.100`.
- TCP port scan (21, 22, 23, 80, 443, 554, 1935, 6123, 6668, 7000, 8000, 8080, 8554, 9000, 20190, 20191, 32108):
  **only 20190 is open**. No telnet, no HTTP, no RTSP.
- UDP discovery on 20190 answered with:
  - DID `PPHA10…` (redacted), firmware `3.00.42.01_241230`, `protocol=pprpc encrypt=3`
  - a stale self-reported IP from a previous Wi-Fi it was once paired with
  - **the device's pairing secret (`$L8$…`), handed out to anyone on the network without authentication.**
    This confirms on the HA10 the issue documented for the INO-A9 boards.
- With that secret, `ipc_LanAuth` (2650) returned a session key. Then `ipc_Hello` (106), 2653, 2645 and
  `ipc_VideoPlay` (2610) all succeeded and the camera streamed MEDIA frames.
- Recovered a valid **640×480 JPEG** (≈16 KB).

**Conclusion:** the A12 / HA10 speaks the same PPRPC protocol as the INO-A9 family, with the same shared prekey.
The existing open-source clients work on it unchanged.

**Security note:** anyone who can join the camera's network (the AP password is the same `12345678` on every
unit) or who is on the same LAN can read the secret and watch the camera. Keep these cameras on an isolated
network segment.
