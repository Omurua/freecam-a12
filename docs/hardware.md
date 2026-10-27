# Hardware

## Known so far

| Item | Value | Source |
|---|---|---|
| Marketing name | "A12" HD Wi-Fi camera, black | AliExpress listing |
| App | Linklemo (`com.xcthings.fchan`) | Owner |
| Setup AP SSID prefix | `LLM_` | Owner |
| Setup AP password | `12345678` (factory default, same on every unit) | Owner |
| PCB marking | _TODO, open the case and photograph the board_ | |
| SoC | _TODO, probably Beken BK7252N_ | Similar INO-A9 boards |
| Flash chip | _TODO_ | |
| Image sensor | _TODO_ | |
| UART pads | _TODO_ | |

## How to fill this in

1. Open the case and take sharp photos of both sides of the PCB. Add them to `docs/img/`.
2. Write down every marking on the main chip, the flash (an 8-pin SOIC) and the sensor ribbon.
3. Look for 3 or 4 pads labelled `TX`, `RX`, `GND` (and maybe `3V3`). That is the serial console.

## Related boards

- `INO-A9-V2.8`, `INO-IPC-A9`, `INO-A10N-V2.3`: same vendor (XC Things), BK7252N, PPRPC on port 20190
- Linklemo/XCThings HA15 Pocket MiniCam: BK7252UQN48 ([elektroda thread](https://www.elektroda.com/rtvforum/topic4150112.html))
