# tools/

Our own helper scripts. They reuse the PPRPC implementation from a local checkout of
[zkiiito/A9](https://github.com/zkiiito/A9) instead of rewriting it, and need the shared prekey in `$env:A9_PREKEY`
(documented in the public analyses linked from that repo; never commit it here).

| Script | What it does |
|---|---|
| [`probe_ap.ps1`](probe_ap.ps1) | Joins the camera's setup AP, scans ports, runs discovery and grabs one snapshot, then returns to your home Wi-Fi |
| [`a12_wifi.py`](a12_wifi.py) | `--show` / `--scan` / `--ssid NAME`: read the stored Wi-Fi, list networks the camera sees, or move it onto your Wi-Fi (`WifiSet`, 2602). The passphrase is asked interactively |
| [`setup_wifi.ps1`](setup_wifi.ps1) | Whole flow on Windows: AP → scan → confirm → `WifiSet` → back home → find the camera on the LAN by MAC → snapshot |

`a12_wifi.py --probe` sends only read-only commands and reports which ones the firmware answers; add `--debug`
to see every frame. Commands must wait for the camera's heartbeats after connecting, or it ignores them.

The Windows scripts are written for PCs whose only internet link is Wi-Fi: they always reconnect to the home
network at the end. Results go to `captures/` (gitignored).

## Notes

- The camera accepts **one session at a time** and needs ~8 s between sessions. Stop any running stream
  before using these tools.
- It is 2.4 GHz only. If it never joins your network, check the router's channel (1–11 is safest) and band.
- Undo: hold MODE ~15 s, or power-cycle it several times, and the `LLM_` AP comes back.

## Live video

Once the camera is on your LAN:

```
pip install av numpy
python <A9 checkout>\a9_mjpeg_server.py --config captures\setup\a9_camera.json
```

Then open http://127.0.0.1:8080/ (MJPEG at `/stream.mjpg`, video + audio for VLC at `/live.ts`).
