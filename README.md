# freecam-a12

Free the **"A12" mini Wi-Fi camera** (Linklemo / XC Things) from the vendor cloud.
Your images stay on your network. No account, no app, no servers in another country.

> 🇪🇸 [Leer en español](README.es.md)

## Status

🚧 **Early research.** Nothing here is ready for end users yet.

✅ **2026-10-27:** first snapshot taken fully offline (no app, no account, no internet). The A12 is internally an
**HA10** and speaks the same PPRPC protocol as the INO-A9 cameras. See [docs/findings.md](docs/findings.md).

## Is this my camera?

| Clue | Value |
|---|---|
| Vendor app | **Linklemo** (`com.xcthings.fchan`) |
| Setup Wi-Fi (AP mode) | SSID starts with **`LLM_`** |
| Likely SoC | Beken **BK7252N** (to be confirmed, see [docs/hardware.md](docs/hardware.md)) |
| Likely protocol | XC Things **PPRPC** on TCP/UDP port **20190** |

If your camera uses the **V720 / Naxclow** app (port 6123) or **HDWiFiCam Pro / YsxLite** (PPPP), it is a
different family. See [Related projects](#related-projects).

## Goals

1. **Identify** the hardware and confirm which protocol family the A12 belongs to.
2. **Local streaming now:** document how to run the camera fully offline (isolated VLAN, internet blocked)
   using the existing open-source clients, and contribute fixes upstream where needed.
3. **Cloud-free firmware later:** study the BK7252N firmware and work towards a replacement that never phones home
   and exposes a standard stream (MJPEG/RTSP). No open firmware has camera support for this chip yet.

## Repository layout

```
docs/       Findings: hardware, protocol, network behaviour, AI-assisted RE workflow
tools/      Our own scripts (capture parsing, helpers)
captures/   Network captures (gitignored, never publish them, they contain your device secrets)
firmware/   Flash dumps (gitignored, vendor firmware is not redistributable)
```

## Related projects

This project stands on the shoulders of others. Many thanks to:

- [IvanFogel/ino-a9-local-bridge](https://github.com/IvanFogel/ino-a9-local-bridge): local PPRPC client, MJPEG bridge and
  Home Assistant integration for the `LLM_` INO-A9 cameras (0BSD)
- [zkiiito/A9](https://github.com/zkiiito/A9): standalone local client and protocol write-up (MIT)
- [laloshifrin/A9](https://github.com/laloshifrin/A9): fork of the above with audio support
- [intx82/a9-v720](https://github.com/intx82/a9-v720): V720 / Naxclow family
- [DavidVentura/cam-reverse](https://github.com/DavidVentura/cam-reverse): iLnk / PPPP family
- [daniel-dona/beken7252-opencam](https://github.com/daniel-dona/beken7252-opencam): alternative RT-Thread firmware for BK7252 cameras

## Legal and ethics

Only use this on devices **you own**. This project contains no vendor firmware and no vendor keys.
It exists for privacy and interoperability.

## License

[MIT](LICENSE)
