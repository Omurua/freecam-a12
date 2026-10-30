# Findings

Lab notes, newest first. Device identifiers (DID, MAC suffix, secrets) are redacted.

## 2026-10-30: root shell over Wi-Fi via telnet ✅ (no soldering)

Lead from [Protoser/bk7252-cam-reverse-eng](https://github.com/Protoser/bk7252-cam-reverse-eng), which documents an
identical unit (`hardwareVer INNO-IPC-48N-V2.2`, `IOTSDK 3.00.42.01_241230`, `LLM_HA10_*` AP) with a telnet server
on TCP **20023**, login **`root` / `123`**.

Confirmed on our camera, in its `LLM_` softAP mode (camera at `192.168.9.252`):

- Port scan: **TCP 20023 open**, as well as 20190. (Our earlier 17-port scan had not included 20023.)
- A raw TCP client logged in with password `123` and got the banner `Wellcome use telnet` and an **RT-Thread finsh
  `msh />` shell**. Background log lines (`[xm]led on/off`, `jpeg fps`) are interleaved with command output.
- **This is a root shell reached purely over Wi-Fi, no UART and no soldering.** It does not need the torn-off pads.

Why it matters in principle: the shell has `fal` (Flash Abstraction Layer) with `fal probe <part>` and
`fal read <off> <len>` (hexdump) — a flash **backup** path with no bootloader (`fal erase` must never be run).

**But driving commands over this telnet is, so far, not working.** After login we only get the banner and the
periodic background log; `help`, `fal probe app` and `fal read` produced no visible command output, even with a
45 s read window. This matches the Protoser notes: in softAP the camera endlessly retries the unreachable cloud,
which **freezes the single network thread for ~30 s at a time**, and the camera **reboots often**, killing the
telnet session. That project dumped the flash over the **UART serial** shell for exactly this reason, and only
*expected* the telnet shell to behave the same — they did not record a working command over telnet.

Update: **TCP 20023 is open in station mode too** (camera on the LAN at a normal address, cloud reachable). So the
cloud-thrash theory is not the whole story. With the camera on the LAN with working internet, and with a proper
telnet client that handles IAC negotiation (`tools/cam_shell.py`, Python `telnetlib`), **login still succeeds but
typed commands still return no output** — `version`, `fal probe app`, `fal read` all produce only the periodic
background log, and the login/banner itself is intermittent. Tried: raw TCP and telnetlib, `\r\n`/`\n`/`\r` line
endings, read windows up to 45 s, softAP and station mode.

Conclusion so far: this firmware answers the telnet password and prints its console log, but does not give a usable
interactive finsh shell over telnet for us. The Protoser project drove `fal` over the **UART serial** shell, not
telnet, and only assumed telnet would behave the same. A flash dump therefore still needs the serial pads, which are
gone on our unit. The telnet login remains a confirmed, no-soldering foothold for anyone who can get command I/O
working (e.g. correct finsh line discipline, or a more stable network moment).

Mind that the softAP password is the factory `12345678`, so anyone nearby can also reach this shell; keep the camera
powered off when not testing.

## 2026-10-30: listing SD recordings over the LAN

`a12_wifi.py --probe-more` sends commands that look read-only, with empty requests.

- `HistoryDayList` (2624) returned six 60-second entries, `202610310216` to `202610310221`, each with a millisecond
  timestamp, a duration and a time-based name. They match the `.avi` files seen on the card (`16` to `20`); `21` was
  not in that earlier listing. Names run about UTC+8.
- `HistoryDays` (2623) and `DirList` (2703) answered with `code=0` but empty, maybe because they need parameters.
- `OsdGet` (2686), `FileThumList` (2708) and `DeviceGetUserList` (1053) did not answer.
- Downloading a recording has not been tried.

## 2026-10-30: listing SD recordings over the LAN ✅

`a12_wifi.py --probe-more` sends 16 commands whose names suggest they are read-only, with empty requests, from the
setup AP with a card inserted and no cloud or app involved.

**`HistoryDayList` (2624) returns the recordings on the card.** The list matched the files seen on the card, plus one
newer clip recorded in between. Each entry in field 2:

| Field | Example meaning | Notes |
|---|---|---|
| 1 | Start time in ms | Unix time |
| 3 | `60000` | Clip length in ms |
| 4 | Start time in s | Unix time |
| 5 | `YYYYMMDDHHMM` | Maps to `/sd/YYYYMMDD/HH/MM.avi` |
| 6 | `255` | Unknown |

- The `HHMM` label and folder names look like UTC+8, not local time. This comes from comparing a few timestamps by hand.
- Answered but empty when sent without parameters: `HistoryPlanGet`, `HistoryDays`, `MotionzoneGet`, `TimedcruiseGet`,
  `PowerFreqGet`, `VolumeGet`, `EventRecordGet`, `DirList`.
- Answered with values we have not interpreted: `NotifyGet`, `AlarmGet`, `PirGet`, `ChanState`.
- No reply: `OsdGet`, `FileThumList`, `DeviceGetUserList`.
- Not attempted: downloading a clip (`HistoryPlay` 2625 or `FileStart` 2690, formats unknown), `LogSet`, `CustomCmd`.

This does not help with loading other firmware. It only shows what the stock app allows.

## 2026-10-30: listing SD recordings over the local network ✅

`a12_wifi.py --probe-more` sends empty requests to commands whose names suggest read-only behaviour, in AP mode with
a card inserted. `HistoryDayList` (2624) lists the recordings, without the cloud or removing the card:

```
{1: 1793384160000, 3: 60000, 4: 1793384160, 5: 202610310216, 6: 255}
```

| Field | Meaning (inferred) |
|---|---|
| 1 | Start time in milliseconds |
| 3 | Duration in milliseconds: one minute |
| 4 | Start time in seconds |
| 5 | `YYYYMMDDHHMM` in **UTC+8** (field 4 is 18:16 UTC), matching the card's `/20261031/02/16.avi` path |
| 6 | Unknown, always 255 |

Entries appeared in step with the one-minute files on the card, newest first.

Other replies: `NotifyGet`, `AlarmGet`, `PirGet` and `ChanState` return small settings whose meaning is unknown.
`HistoryPlanGet`, `HistoryDays`, `MotionzoneGet`, `TimedcruiseGet`, `PowerFreqGet`, `VolumeGet`, `EventRecordGet` and
`DirList` answer empty, possibly because they need parameters. `OsdGet`, `FileThumList` and `DeviceGetUserList` do not
answer.

Downloading a recording over the network (`HistoryPlay` 2625, `FileStart` 2690) has not been tried.

## 2026-10-30: microSD firmware load, no result so far ❌

Goal: load another firmware without soldering. The bootloader of a sibling board's public dump mentions a file
`RTTHREAD.RBL` on the SD card. This has not been confirmed on our unit, and no public report of this route was found.

**Tested:** official `OpenBK7252N_1.18.320.rbl` copied unmodified as `RTTHREAD.RBL` to the root of a FAT32 partition
(first of two on an MBR card). Header: magic `RBL`, partition `app`, algorithm `0x102` (encrypted and compressed),
valid CRCs. Cold boot normally, then cold boot holding the button for ~10 s.

**Result:** the `LLM_` network came back both times and no `OpenBK` network appeared. The camera survived.

- `StorageInfo` (2653) changed from `{1: 4}` without a card to `{2: 508, 3: 28}`: the app mounts the 0.5 GB partition.
- Without UART we cannot tell why it did nothing. Possibilities: this bootloader does not use the card in this
  situation, or it rejected the file (algorithm or key).

**Also tested:** the same file on a card with a single FAT32 partition: same result, `LLM_` came back.

Afterwards the card held `RTTHREAD.RBL` byte-identical to the original, plus recordings the app wrote by itself:
`/<YYYYMMDD>/<HH>/<MM>.avi` with one `.jpg` thumbnail per file, about 8-10 MB per minute. So the app reads and writes
this card, while the update file was left untouched. No log or other diagnostic file appeared.

UART output is the most useful next step, but our TX/RX pads are gone. The LED patterns vary too much to be useful.

## 2026-10-27: on the home Wi-Fi without the app ✅

- [`tools/setup_wifi.ps1`](../tools/setup_wifi.ps1) sent `WifiSet` (2602) with the home SSID; the camera answered
  `code=0` and joined the home network within a minute, from the station MAC predicted by `GetNetworkInfo`.
- **UDP broadcast discovery got no answer on the home LAN** (it did in AP mode). The camera was found instead by
  its Beken MAC prefix in the ARP table; the setup script now does that.
- A snapshot over the home LAN with the saved DID + secret worked: 640×480 JPEG.
- **Continuous video works** over the home LAN with zkiiito's `a9_mjpeg_server.py` (`pip install av numpy`),
  viewed in the browser at `http://127.0.0.1:8080/`.
- The `LLM_` setup AP still showed up in Windows' network list ~5 minutes after the camera joined the home
  network, but **was gone ~12 minutes after**, with the camera still on the LAN. Either the AP lingers for a few
  minutes or Windows was showing cached scan results; in both cases it does not stay up in station mode.

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
