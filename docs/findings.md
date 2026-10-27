# Findings

Lab notes, newest first. Device identifiers (DID, MAC suffix, secrets) are redacted.

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
