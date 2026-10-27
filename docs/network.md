# What the camera sends to the internet

Captured on 2026-10-27 with [`tools/capture_hotspot.ps1`](../tools/capture_hotspot.ps1) (PC as the camera's
router, `pktmon`), 10 minutes, camera **idle**: no app, no account bound today, nobody watching the stream.
Decoded with [`tools/analyze_pcap.py --decrypt`](../tools/analyze_pcap.py). Device identifiers are redacted:
`<DID>` = device ID (`PPHA10…`), `<TOKEN>` = a 12-character per-device credential, `<MAC>` = station MAC.

## Summary

- **One DNS lookup at start-up only:** `prod.glbs.xcthings.com` → `47.240.1.244` (seen in the second, two-way
  capture with a reboot). The firmware also carries that IP and three more (`47.252.5.225`, `8.209.77.49`,
  `39.108.59.60`) as hardcoded fallbacks, and every later server comes from the `GetServers` answer, not from DNS.
  So a DNS blocker (Pi-hole, AdGuard) is **not enough**: block the camera by MAC/IP on the router.
- All three servers are **Alibaba Cloud**:

  | IP | Owner (RDAP) | Used for |
  |---|---|---|
  | `47.240.1.244` UDP 465 | Alibaba Cloud, Hong Kong | Bootstrap: asks which servers to use (`GetServers`, once at start-up) |
  | `8.209.73.117` UDP 80 | Alibaba Cloud, Germany (`ALICLOUD-DE`) | Messaging channel (MQTT-like "PPMQ"), keepalive every ~17 s |
  | `8.209.74.201` TCP 80 and 465 | Alibaba Cloud, Germany (`ALICLOUD-DE`) | `CSCfg`: asks for its **cloud storage** configuration, every ~60 s |

- Everything is PPRPC encrypted with the **shared prekey** that is the same in every unit, so anyone on the
  path can decrypt it (we did).
- **Volume: ~6 KB sent in 10 minutes.** No images or video were uploaded while idle.

## What it says (decrypted)

| When | Command | Content |
|---|---|---|
| start | `601 GetServers` → HK | `<DID>`, `<TOKEN>`, timestamp |
| start | `12` → DE | `<DID>`, `<TOKEN>`, **station `<MAC>`** |
| start | `17` → DE | Two topics: `/notify/conn/<DID>` and **`/xc/2d/cmd/<DID>`**. Looks like a subscription to a per-camera **remote command** topic |
| start, then every 1–8 min | `13` → DE | Publishes to `/xc/2p/state` (firmware `3.00.42.01_241230`, a second component `3.00.21.01_250726`, board **`INNO-IPC-48N-V2.2`**) and to `/xc/2p/event` (small 11-byte event blob) |
| every ~17 s | `19` → DE | Empty keepalive |
| every ~60 s | `1101 CSCfg` → DE (TCP) | `<TOKEN>`, `<DID>`: asks for the cloud-storage (recording upload) settings; repeats, so it apparently never gets a configuration it can use |

Command names come from [cheap-shot](https://github.com/Yeti47/cheap-shot)'s table. For 12/13/17/19 the payloads
do not match those names exactly (e.g. 17 carries topics, like a subscribe), so read them as approximate.

## What this means

- With internet access the camera keeps an **open, always-on channel to Alibaba Cloud** identifying itself
  (device ID, token, MAC, firmware) and listens on a **command topic** for its own ID. That channel is how the
  vendor app reaches it from outside, and the vendor (or anyone holding the token) can push commands through it.
- It keeps asking for **cloud recording** settings. We saw no upload while idle and without a subscription, but
  the capability is there.
- The traffic is identical in kind to what other users reported for INO-A9 cameras (ports 80/465/8000).

## Second capture: both directions, with a reboot (2026-10-27)

[`capture_hotspot.ps1 -Wireshark -Reboot`](../tools/capture_hotspot.ps1), 15 minutes, `dumpcap` on the hotspot
adapter filtered by the camera's MAC, camera power-cycled right after the start. ~5 KB each way.

What the cloud answers (decrypted with the same shared prekey):

| Request | Answer |
|---|---|
| `601 GetServers` | Server directory: types 1 and 2 → `8.209.73.117:1053`, type 6 → `8.209.74.201:465`, type 8 → `47.254.174.22` and `47.91.79.195`, type 15 → `47.254.174.22`, types 18/19 → `8.209.74.201` |
| `12` (client ID) | Two timestamps and **the home's public IP address as seen by the cloud** (redacted here) |
| `17` (topics) | Echoes `/notify/conn/<DID>` and `/xc/2d/cmd/<DID>` back: the command topic subscription is accepted |
| `13` (publish state / dp) | A 32-hex-character id per message |
| `19` keepalive | Empty, answered every ~28 s |
| `1101 CSCfg` | `{3: {6: "0b"}}`: apparently "no cloud storage configured" |

- **No firmware check (`FirmwareCheck` 921 / `FirmwareNotify` 2670) and no command** arrived in 15 minutes,
  including the boot. Firmware updates are probably only checked when the vendor app asks, or on a long timer.
- The cloud learns the household's **public IP** on every connection.

## Limitations of this capture

- First capture: `pktmon` only stored the camera's **outgoing** packets. Fixed in the second one.
- 10 and 15 minutes idle only: no motion events, no app session, no long-term behaviour (daily firmware checks?).

## Recommendation

Block the camera's MAC from the internet on the router. Local viewing (`tools/`) keeps working, since it only
uses TCP 20190 on the LAN.
