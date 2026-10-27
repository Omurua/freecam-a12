# Hardware

## Known so far

| Item | Value | Source |
|---|---|---|
| Marketing name | "A12" HD Wi-Fi camera, black | AliExpress listing |
| App | Linklemo (`com.xcthings.fchan`) | Owner |
| Internal model | **HA10** (from SSID and DID prefix `PPHA10…`) | Probe 2026-10-27 |
| Setup AP SSID | `LLM_HA10_<6 digits>` | Probe 2026-10-27 |
| Setup AP password | `12345678` (factory default, same on every unit) | Owner |
| Setup AP radio | 802.11g, 2.4 GHz | Probe 2026-10-27 |
| Camera IP in AP mode | `192.168.9.252` (DHCP gives the client `192.168.9.100`) | Probe 2026-10-27 |
| MAC OUI | `c8:47:8c` (Beken Corporation) | Probe 2026-10-27 |
| Firmware | `3.00.42.01_241230` | PPRPC discovery reply |
| USB | Power only, no data device enumerates on the host | Probe 2026-10-27 |
| PCB marking | _TODO, needs opening the case_ | |
| SoC | _TODO, very likely Beken BK7252N_ | MAC OUI + related boards |
| Flash chip | _TODO_ | |
| Image sensor | _TODO_ | |
| UART pads | _TODO_ | |

## How to fill in the rest

1. Open the case and take sharp photos of both sides of the PCB. Add them to `docs/img/`.
2. Write down every marking on the main chip, the flash (an 8-pin SOIC) and the sensor ribbon.
3. Look for 3 or 4 pads labelled `TX`, `RX`, `GND` (and maybe `3V3`). That is the serial console.

## Related boards

- `INO-A9-V2.8`, `INO-IPC-A9`, `INO-A10N-V2.3`: same vendor (XC Things), BK7252N, PPRPC on port 20190
- Linklemo/XCThings HA15 Pocket MiniCam: BK7252UQN48 ([elektroda thread](https://www.elektroda.com/rtvforum/topic4150112.html))
