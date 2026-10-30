# Roadmap

## Phase 0: identification
- [x] Photograph the PCB and identify the SoC, flash and sensor: `INO-A10N-V2.3`, BK7252N, GC0329 ([hardware.md](hardware.md))
- [x] Connect to the `LLM_` AP and scan open ports (only TCP 20190 is open)
- [x] Confirm PPRPC on port 20190 by running the existing clients against the camera ([findings](findings.md))

## Phase 1: local streaming without the cloud
- [x] Get a snapshot with [zkiiito/A9](https://github.com/zkiiito/A9) (640×480 JPEG, fully offline)
- [x] Get a continuous MJPEG stream (`a9_mjpeg_server.py` from zkiiito/A9)
- [x] Provision the camera onto home Wi-Fi without a Linklemo account (`tools/setup_wifi.ps1`)
- [x] Confirm whether the `LLM_` AP stays up in station mode (it does not, see [findings](findings.md))
- [ ] Document a firewall/VLAN setup that blocks all its internet traffic
- [x] Record which hosts it tries to reach in [network.md](network.md) (hardcoded Alibaba Cloud IPs, no DNS)
- [ ] Capture both directions to see what the cloud answers and whether it sends commands
- [ ] Send any A12-specific fixes upstream

## Phase 2: firmware
- [x] Find the UART console and capture the boot log ([hardware.md](hardware.md))
- [ ] Dump the flash (keep a backup and **never** publish it). Blocked on our unit: the UART pads were torn off
- [ ] **microSD route (open research):** the RT-Thread OTA bootloader references an update file on the SD card
      (`RTTHREAD.RBL`). Learn from RT-Thread's public OTA documentation and the BK7252 community
      ([beken7252-opencam](https://github.com/daniel-dona/beken7252-opencam), Elektroda) when and how it is used,
      and first test it only with an official, unmodified firmware image. An official OpenBeken RBL had no effect so
      far, see [findings](findings.md)
- [ ] The app also reads a factory file `/sd/config_json.txt` (`wifi_ssid`, `wifi_key`, `led_time`, `test_mode`):
      possible app-less Wi-Fi setup, untested
- [ ] Analyse it with Ghidra and an AI assistant (GhidraMCP / REA), see [ai-workflow.md](ai-workflow.md)
- [ ] Find where the cloud endpoints are configured and whether they can be disabled
- [ ] Evaluate a replacement firmware (beken7252-opencam, OpenBK7252) with a camera driver
