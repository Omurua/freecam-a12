#!/usr/bin/env python3
"""
cam_shell.py - talk to the camera's RT-Thread telnet shell (TCP 20023) and run finsh commands.

The camera's telnet does real IAC negotiation, so a raw TCP client logs in only intermittently; telnetlib
handles the negotiation, which makes login and command I/O reliable. Login is password-only (`123` by default).

The shell is noisy: the firmware prints a periodic background log that is interleaved with command replies, so
each command's output is read for a fixed window and the known log lines are filtered out.

    python tools/cam_shell.py 192.168.0.28 --cmd "fal probe app" --cmd "fal read 0x0 0x40"

Works whether the camera is in softAP mode (192.168.9.252) or a station on your LAN. Standard library only
(telnetlib, deprecated but present in Python 3.12).
"""
import argparse, re, sys, time
import telnetlib

NOISE = re.compile(r"\[xm\]led|jpeg fps:|^date: 20|audio:len|vbat volt|->fps=|xvideo\.c|"
                   r"\[pprpc|\[iot\.dev|pprpc_|iot_dev_|GetServers|xglbs|osal_|pool size|ITCM|TCM |heap ")

def connect(host, port, password, timeout):
    t = telnetlib.Telnet(host, port, timeout=timeout)
    # Wait for a password prompt (pwd>> or password>>), then send the password.
    t.read_until(b">> ", timeout=timeout)
    t.write(password.encode() + b"\r\n")
    # Confirm we reached the shell.
    idx, _, _ = t.expect([b"Wellcome use telnet", b"Wrong password"], timeout=timeout)
    if idx != 0:
        # one retry: the first line may have been consumed by a wrong-password cycle
        t.write(password.encode() + b"\r\n")
        idx, _, _ = t.expect([b"Wellcome use telnet", b"Wrong password"], timeout=timeout)
        if idx != 0:
            raise SystemExit("login failed (no 'Wellcome' banner)")
    time.sleep(0.5)
    t.read_very_eager()  # drain the banner
    return t

def run(t, cmd, window):
    t.read_very_eager()
    t.write(cmd.encode() + b"\r\n")
    end = time.time() + window
    buf = b""
    while time.time() < end:
        buf += t.read_very_eager()
        time.sleep(0.2)
    text = buf.decode("ascii", "replace")
    text = "".join(ch if 32 <= ord(ch) < 127 or ch in "\r\n" else "." for ch in text)
    lines = [l for l in text.replace("\r", "").split("\n") if l.strip() and not NOISE.search(l)]
    return lines

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("host")
    ap.add_argument("--port", type=int, default=20023)
    ap.add_argument("--password", default="123")
    ap.add_argument("--timeout", type=float, default=10.0)
    ap.add_argument("--window", type=float, default=4.0, help="seconds to read each command's reply")
    ap.add_argument("--cmd", action="append", default=[], help="command to run (repeatable)")
    a = ap.parse_args()
    if not a.cmd:
        a.cmd = ["version"]
    t = connect(a.host, a.port, a.password, a.timeout)
    print("[*] logged in")
    try:
        for cmd in a.cmd:
            print(f"===== {cmd} =====")
            for l in run(t, cmd, a.window):
                print("  " + l)
    finally:
        t.close()

if __name__ == "__main__":
    main()
