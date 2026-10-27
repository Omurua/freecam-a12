# What the camera sends to the internet

Captured on 2026-10-27 with [`tools/capture_hotspot.ps1`](../tools/capture_hotspot.ps1) (PC as the camera's
router, `pktmon`), 10 minutes, camera **idle**: no app, no account bound today, nobody watching the stream.
Decoded with [`tools/analyze_pcap.py --decrypt`](../tools/analyze_pcap.py). Device identifiers are redacted:
`<DID>` = device ID (`PPHA10…`), `<TOKEN>` = a 12-character per-device credential, `<MAC>` = station MAC.

## Summary

- **No DNS at all.** The servers are hardcoded IP addresses, so DNS-based blockers (Pi-hole, AdGuard) cannot
  stop it. Block it by MAC/IP on the router instead.
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

## Limitations of this capture

- `pktmon` only stored the camera's **outgoing** packets: we know the servers answered (TCP handshakes and
  sessions completed) but not **what** they answered, nor whether they sent commands.
- 10 minutes idle only: no motion events, no app session, no long-term behaviour (firmware update checks).
- Next: capture both directions (e.g. Wireshark on the hotspot adapter) and a longer window.

## Recommendation

Block the camera's MAC from the internet on the router. Local viewing (`tools/`) keeps working, since it only
uses TCP 20190 on the LAN.
