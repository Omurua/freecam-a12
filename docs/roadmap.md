# Roadmap

## Phase 0: identification
- [ ] Photograph the PCB and identify the SoC, flash and sensor ([hardware.md](hardware.md))
- [x] Connect to the `LLM_` AP and scan open ports (only TCP 20190 is open)
- [x] Confirm PPRPC on port 20190 by running the existing clients against the camera ([findings](findings.md))

## Phase 1: local streaming without the cloud
- [x] Get a snapshot with [zkiiito/A9](https://github.com/zkiiito/A9) (640×480 JPEG, fully offline)
- [x] Get a continuous MJPEG stream (`a9_mjpeg_server.py` from zkiiito/A9)
- [x] Provision the camera onto home Wi-Fi without a Linklemo account (`tools/setup_wifi.ps1`)
- [x] Confirm whether the `LLM_` AP stays up in station mode (it does not, see [findings](findings.md))
- [ ] Document a firewall/VLAN setup that blocks all its internet traffic
- [ ] Record which hosts it tries to reach (DNS log) in `docs/network.md`
- [ ] Send any A12-specific fixes upstream

## Phase 2: firmware
- [ ] Find the UART console and capture the boot log
- [ ] Dump the SPI flash (keep a backup and **never** publish it)
- [ ] Analyse it with Ghidra and an AI assistant (GhidraMCP / REA), see [ai-workflow.md](ai-workflow.md)
- [ ] Find where the cloud endpoints are configured and whether they can be disabled
- [ ] Evaluate a replacement firmware (beken7252-opencam, OpenBK7252) with a camera driver
