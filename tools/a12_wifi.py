#!/usr/bin/env python3
"""
a12_wifi.py - read or set the Wi-Fi network the A12 / HA10 camera joins, without the vendor app.

Run it while joined to the camera's setup AP (LLM_xxx, camera at 192.168.9.252).
It authenticates over PPRPC with the camera's own secret (from discovery) and sends:

    --show        WifiGet   (2603)  print the station SSID the camera has stored
    --scan        WifiAPGet (2601)  list the networks the camera can see
    --ssid NAME   WifiSet   (2602)  store NAME + passphrase; the camera leaves AP mode and joins it

The passphrase is asked interactively (never pass it on the command line, it would land in your
shell history). Protocol details: https://github.com/Yeti47/cheap-shot/blob/main/docs/protocol.md

Reuses the protocol helpers from a local checkout of https://github.com/zkiiito/A9 (--client),
and needs the shared prekey in $A9_PREKEY.

If the credentials are wrong the camera will not come back on its own: hold its MODE button
~15 s (or power-cycle it repeatedly) to force AP mode back.
"""
import argparse, getpass, os, socket, sys, time

CMD_WIFIAPGET = 2601
CMD_WIFISET   = 2602
CMD_WIFIGET   = 2603
MAX_WIFI_FIELD = 64

# Read-only commands for --probe (names from cheap-shot's command table). 2653 is known to answer on the HA10
# and acts as the control: if it replies and the others do not, the firmware lacks them.
PROBE_CMDS = [
    (2653, "StorageInfo"), (2603, "WifiGet"), (2601, "WifiAPGet"), (2630, "ConfigGet"),
    (2632, "TimeGet"), (2634, "LedGet"), (2636, "IRCutGet"), (2649, "FlipGet"),
    (2685, "GetNetworkInfo"), (2638, "SecretGet"),
]

# --probe-more: names suggest read-only, but their request formats are undocumented, so they are sent empty.
# LogSet (2656) and CustomCmd (2699) are left out on purpose: one changes settings, the other is unknown.
PROBE_MORE_CMDS = [
    (2622, "HistoryPlanGet"), (2623, "HistoryDays"), (2624, "HistoryDayList"), (2640, "NotifyGet"),
    (2642, "MotionzoneGet"), (2652, "TimedcruiseGet"), (2659, "PowerFreqGet"), (2660, "VolumeGet"),
    (2662, "AlarmGet"), (2666, "PirGet"), (2667, "ChanState"), (2680, "EventRecordGet"),
    (2686, "OsdGet"), (2703, "DirList"), (2708, "FileThumList"), (1053, "DeviceGetUserList"),
]

def load_client(path):
    path = os.path.abspath(path)
    if not os.path.isfile(os.path.join(path, "a9_proto.py")):
        sys.exit(f"{path} does not look like a zkiiito/A9 checkout (no a9_proto.py)")
    sys.path.append(path)
    import a9_proto, a9_discover
    return a9_proto, a9_discover

def reply_code(P, body):
    """CTRL replies (rpc=1) carry a trailing varint result code after the flag byte; 0 = OK."""
    p = 0
    _, p = P.dec_varint(body, p)
    _, p = P.dec_varint(body, p)
    p += 1
    code, _ = P.dec_varint(body, p)
    return code

class Session:
    def __init__(self, P, ip, did, secret, timeout, debug=False):
        self.P, self.timeout, self.debug = P, timeout, debug
        self.s = socket.create_connection((ip, P.PORT), timeout=timeout)
        self.rdr = P.FrameReader(self.s)
        self.seq = 3
        self._send(P.CMD_LANAUTH, P.pb_field_bytes(2, did) + P.pb_field_bytes(3, secret))
        if not self._wait_reply(P.CMD_LANAUTH):
            sys.exit("LanAuth failed (wrong secret, or another client is still connected: wait ~8 s)")
        self._send(P.CMD_HELLO, P.pb_varint_field(1, 1))
        self._wait_reply(P.CMD_HELLO)
        # Like cheap-shot: let the camera's own heartbeats arrive and answer them before any command.
        self._pump(2.0)

    def _send(self, cmd, plaintext=b""):
        if self.debug: print(f"    -> cmd={cmd} seq={self.seq} len={len(plaintext)}")
        self.s.sendall(self.P.build_ctrl(self.seq, cmd, plaintext))
        self.seq += 1

    def _pump(self, dur):
        """Read and log frames for dur seconds, answering heartbeats."""
        P = self.P
        end = time.time() + dur
        while time.time() < end:
            try:
                mt, _, body = self.rdr.next_frame(timeout=max(0.1, end - time.time()))
            except TimeoutError:
                return
            if mt == 4:
                cmd, rseq, rpc, ct = P.ctrl_exhdr(body)
                if self.debug: print(f"    <- CTRL cmd={cmd} seq={rseq} rpc={rpc} len={len(ct)}")
                if rpc == 0:
                    self._answer_heartbeat(cmd, rseq, ct)
            elif self.debug:
                print(f"    <- type={mt} len={len(body)}")

    def _answer_heartbeat(self, cmd, rseq, ct):
        P = self.P
        if cmd == P.CMD_PING:
            pt = P.ctrl_decrypt(cmd, rseq, 0, ct)
            echo = P.pb_parse(pt).get(1, [0])[0] if pt else 0
            pong = (P.pb_varint_field(1, echo) + P.pb_varint_field(2, P.HB_CONST)
                    + P.pb_varint_field(3, int(time.time() * 1000)))
            self.s.sendall(P.build_ctrl(rseq, P.CMD_PING, pong, flag=0x0D))
        elif cmd == P.CMD_HELLO:
            self.s.sendall(P.build_ctrl(rseq, P.CMD_HELLO, P.pb_varint_field(1, 1), flag=0x0D))

    def _wait_reply(self, want_cmd):
        """Return (code, decoded protobuf fields) of the reply to want_cmd, or None on timeout."""
        P = self.P
        end = time.time() + self.timeout
        while time.time() < end:
            try:
                mt, _, body = self.rdr.next_frame(timeout=max(0.2, end - time.time()))
            except TimeoutError:
                return None
            if mt != 4:
                if self.debug: print(f"    <- type={mt} len={len(body)}")
                continue
            cmd, rseq, rpc, ct = P.ctrl_exhdr(body)
            if self.debug:
                code = reply_code(P, body) if rpc == 1 else "-"
                print(f"    <- CTRL cmd={cmd} seq={rseq} rpc={rpc} code={code} len={len(ct)}")
            if rpc == 0:
                self._answer_heartbeat(cmd, rseq, ct)
            elif rpc == 1 and cmd == want_cmd:
                pt = P.ctrl_decrypt(cmd, rseq, rpc, ct) if ct else b""
                return reply_code(P, body), (P.pb_parse(pt) if pt else {})
        return None

    def call(self, cmd, plaintext=b""):
        self._send(cmd, plaintext)
        return self._wait_reply(cmd)

    def close(self):
        try: self.s.close()
        except OSError: pass

def text(v):
    return v.decode(errors="replace") if isinstance(v, bytes) else str(v)

def show(P, v):
    """Readable form of a protobuf value: text if printable, else a nested message if it parses, else hex."""
    if not isinstance(v, bytes):
        return v
    if v and all(32 <= c < 127 for c in v):
        return v.decode()
    f = P.pb_parse(v)
    return {k: [show(P, x) for x in xs] for k, xs in f.items()} if f else v.hex()

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--client", required=True, help="path to a zkiiito/A9 checkout")
    ap.add_argument("--ip", default="192.168.9.252", help="camera IP (default: AP-mode address)")
    ap.add_argument("--config", help="a9_camera.json saved by a9_discover.py (else: discover now)")
    ap.add_argument("--timeout", type=float, default=8.0)
    ap.add_argument("--debug", action="store_true", help="log every frame sent/received")
    ap.add_argument("--password-env", metavar="VAR",
                    help="with --ssid: read the passphrase from this environment variable instead of asking")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--probe", action="store_true",
                      help="send read-only commands and report which ones this firmware answers")
    mode.add_argument("--probe-more", action="store_true",
                      help="like --probe, for storage, history and settings commands with undocumented requests")
    mode.add_argument("--show", action="store_true", help="print the stored station SSID")
    mode.add_argument("--scan", action="store_true", help="list networks the camera can see")
    mode.add_argument("--ssid", help="network the camera should join (2.4 GHz only)")
    a = ap.parse_args()

    if a.ssid is not None:
        if not a.ssid or len(a.ssid.encode()) > MAX_WIFI_FIELD:
            sys.exit(f"--ssid must be 1..{MAX_WIFI_FIELD} bytes")
        if a.password_env:
            pwd = os.environ.get(a.password_env)
            if pwd is None:
                sys.exit(f"environment variable {a.password_env} is not set")
        else:
            pwd = getpass.getpass(f"Passphrase for '{a.ssid}' (input hidden): ")
            if pwd != getpass.getpass("Repeat passphrase: "):
                sys.exit("passphrases do not match, nothing sent")
        if len(pwd.encode()) > MAX_WIFI_FIELD:
            sys.exit(f"passphrase must be at most {MAX_WIFI_FIELD} bytes")

    P, D = load_client(a.client)
    ip, did, secret = D.resolve_credentials(a.ip, config=a.config or D.CONFIG_DEFAULT,
                                            no_config=not a.config)
    print(f"[*] camera {ip}, authenticating…")
    sess = Session(P, ip, did, secret, a.timeout, a.debug)
    try:
        if a.probe or a.probe_more:
            sess.timeout = min(a.timeout, 3.0)
            for cmd, name in (PROBE_CMDS if a.probe else PROBE_MORE_CMDS):
                r = sess.call(cmd)
                if r is None:
                    print(f"  {cmd:5d} {name:15s} no reply")
                else:
                    fields = {k: [show(P, x) for x in v] for k, v in r[1].items()}
                    print(f"  {cmd:5d} {name:15s} code={r[0]} {fields}")
        elif a.show:
            r = sess.call(CMD_WIFIGET)
            if r is None: sys.exit("no reply to WifiGet")
            stored = text(r[1].get(2, [b""])[0])
            print(f"stored station SSID: {stored!r}" if stored else "no station SSID stored (AP mode)")
        elif a.scan:
            r = sess.call(CMD_WIFIAPGET)
            if r is None: sys.exit("no reply to WifiAPGet")
            entries = r[1].get(2, [])
            print(f"{len(entries)} network(s) seen by the camera:")
            for e in entries:
                f = P.pb_parse(e) if isinstance(e, bytes) else {}
                fields = {k: text(v[0]) for k, v in f.items()}
                print("  ", fields or text(e))
        else:
            payload = P.pb_field_bytes(2, a.ssid.encode()) + P.pb_field_bytes(3, pwd.encode())
            r = sess.call(CMD_WIFISET, payload)
            if r is None:
                sys.exit("no reply to WifiSet (the camera may still have accepted it: check your router)")
            if r[0] != 0:
                sys.exit(f"camera rejected WifiSet (code {r[0]})")
            print(f"[*] camera accepted the credentials for '{a.ssid}'.")
            print("    It is leaving AP mode now and will ask your router for an IP (DHCP).")
            print("    Find it on your LAN (MAC prefix c8:47:8c) and give it a DHCP reservation.")
    finally:
        sess.close()

if __name__ == "__main__":
    main()
