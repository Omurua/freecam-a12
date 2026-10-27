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
| Station MAC | AP BSSID with the lowest bit cleared (`…:55` → `…:54`) | `GetNetworkInfo` (2685) |
| Firmware | `3.00.42.01_241230` | PPRPC discovery reply |
| USB | Power only, no data device enumerates on the host | Probe 2026-10-27 |
| Board ID (self-reported) | `INNO-IPC-48N-V2.2` | Cloud state message, [network.md](network.md) |
| Second component version | `3.00.21.01_250726` | Cloud state message |
| PCB marking | **`INO-A10N-V2.3 Ca13`** (same board as [laloshifrin/A9](https://github.com/laloshifrin/A9)'s test unit) | Photo |
| SoC | **Beken `BK7252NQN48`** (BK7252N, 48-pin QFN), 26 MHz crystal | Photo |
| Flash | On-chip; RT-Thread FAL reports a 4 MB device, partitions use the first 2 MB | UART boot log |
| Button | `KEY1` next to the crystal: power on/off (long press turns the firmware "off"), not a download-mode strap | UART + tests |
| Other | USB-C (power only), microphone, sensor on an 18-pin FPC (`X5-G29-2364V1`), `LED +/-` pads | Photo |
| Image sensor | **GalaxyCore GC0329** (the firmware probes ~15 sensors over I²C and picks it) | UART boot log |
| microSD slot | Present (`tf_record.c`); fails cleanly when empty | UART boot log |
| UART | Pads silkscreened `TX` / `RX` on the PCB. **115200 8N1**, 3.3 V. App log on TX | UART, 2026-10-27 |

## UART access

Tested with an **ESP32-WROOM-32 DevKit used as a plain USB-serial adapter**: jumper **EN → GND** (keeps the ESP32
in reset so only its CP2102 works), then wire **straight, not crossed**:

| ESP32 DevKit pin | Camera pad |
|---|---|
| `TXD` | `TX` |
| `RXD` | `RX` (not needed just to read the log) |
| `GND` | ground: the USB connector shell worked well; the microSD cage gave a noisy signal |

Lessons learned: crossing the wires with a dormant ESP32 makes the camera's TX fight the CP2102's TX (you read
only zeros); a bad ground gives text with flipped bits; with only `TX` + `GND` the log came out clean.

⚠️ **The `TX`/`RX` through-hole pads (back side, next to the `R10 R13 R14 R3 R2 R7` resistor row) are tiny and
lift easily.** Both were torn off on our unit while re-soldering. Use little heat, tin the wire first, glue the wire
to the board for strain relief, and never pull on it. If a pad lifts, follow its trace to a series resistor or via.

Open issue: with the dormant-ESP32 adapter, connecting the camera's `RX` made the camera stop logging (blue + red LEDs
solid) although `RX` had no continuity to ground, and `bk7231tools` never got a link answer. Not resolved before the
pads were lost. Next time try an awake ESP32/RP2040 running a UART bridge sketch on separate pins.

## Boot chain and flash layout

Cold boot (USB-C unplugged and re-plugged) prints:

- An **RT-Thread OTA bootloader** (`RT-Thread OTA package V0.2.8-beken`, FAL V0.4.0), not Beken's stock UART
  bootloader. It reports `App verify failed! Need to recovery factory firmware` and then boots the app anyway
  (`go os_addr(0x10000)`). This bootloader probably does not speak the Beken UART download protocol, which would
  explain why `bk7231tools` never linked.
- FAL partition table (`beken_onchip_crc` = 32 data + 2 CRC bytes per 34):

  | Partition | Device | Offset | Length |
  |---|---|---|---|
  | bootloader | beken_onchip_crc | `0x000000` | `0x010000` |
  | app | beken_onchip_crc | `0x010000` | `0x110000` |
  | download (OTA) | beken_onchip | `0x132000` | `0x0AE000` |

- App-level table: RF firmware `0x1E0000`, NET info `0x1E1000`, xc config1 `0x1F4000`, xc config `0x1F5000`
  (device secrets live there; never publish a dump without scrubbing them).
- An **RT-Thread `msh />` shell** on the same UART: an alternative way to read flash (`fal` commands) without the
  download mode, if `RX` works.

## What the boot log shows

- Sensor detection loop, then `GC0329C init finish`; JPEG encoder runs continuously at ~10 fps (~100 KB/s
  internally) even when nobody is watching.
- `mjpeg_server_thread` and `start web camerar` in `xdev_video.c`: the firmware has some built-in MJPEG server
  (not reachable on any TCP port we scanned, to investigate).
- `upnpc` (UPnP client) and an `osal_tcp_server` start with the cloud SDK.
- `GetServers` returns a list of cloud services and ports: 80, 1053, 465, 1990, 1991, **554 (RTSP)**, 9125, 8000.
- `rom ver=3.00.21.01_250726`, `hdw ver=INNO-IPC-48N-V2.2`, `AVSDK VER: 3.00.42.01_241230, build: Dec 30 2024`.

## How to fill in the rest

1. Open the case and take sharp photos of both sides of the PCB. Add them to `docs/img/`.
2. Write down every marking on the main chip, the flash (an 8-pin SOIC) and the sensor ribbon.
3. Look for 3 or 4 pads labelled `TX`, `RX`, `GND` (and maybe `3V3`). That is the serial console.

## Related boards

- `INO-A9-V2.8`, `INO-IPC-A9`, `INO-A10N-V2.3`: same vendor (XC Things), BK7252N, PPRPC on port 20190
- Linklemo/XCThings HA15 Pocket MiniCam: BK7252UQN48 ([elektroda thread](https://www.elektroda.com/rtvforum/topic4150112.html))
