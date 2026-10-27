#!/usr/bin/env python3
"""
analyze_pcap.py - summarise what a camera talks to in a pcapng capture (e.g. from capture_hotspot.ps1).

Standard library only. Prints DNS lookups, every remote endpoint (protocol, port, packets, bytes each way,
first/last seen, typical interval) and TLS SNI names. pktmon logs the same packet once per network component,
so duplicates are dropped.

    python tools/analyze_pcap.py captures/traffic-.../camera.pcapng --camera 192.168.137.50
"""
import argparse, collections, hashlib, ipaddress, socket, struct, sys

def read_pcapng(path):
    """Yield (timestamp_seconds, linktype, frame_bytes) from Enhanced/Simple Packet Blocks."""
    data = open(path, "rb").read()
    i, endian, ifaces = 0, "<", []
    while i + 12 <= len(data):
        btype = struct.unpack_from(endian + "I", data, i)[0]
        if btype == 0x0A0D0D0A:                      # Section Header: fixes byte order
            endian = "<" if data[i + 8:i + 12] == b"\x4d\x3c\x2b\x1a" else ">"
            ifaces = []
        blen = struct.unpack_from(endian + "I", data, i + 4)[0]
        if blen < 12 or i + blen > len(data):
            break
        body = data[i + 8:i + blen - 4]
        if btype == 1:                               # Interface Description
            ifaces.append(struct.unpack_from(endian + "H", body, 0)[0])
        elif btype == 6:                             # Enhanced Packet
            iface, th, tl, caplen = struct.unpack_from(endian + "IIII", body, 0)
            ts = ((th << 32) | tl) / 1e6             # pktmon uses the default microsecond resolution
            lt = ifaces[iface] if iface < len(ifaces) else 1
            yield ts, lt, body[20:20 + caplen]
        i += blen

def ip_packet(linktype, frame):
    """Return the IPv4 packet inside a frame, or None."""
    if linktype == 1:                                # Ethernet
        if len(frame) < 14: return None
        et, off = struct.unpack(">H", frame[12:14])[0], 14
        if et == 0x8100: et, off = struct.unpack(">H", frame[16:18])[0], 18
        return frame[off:] if et == 0x0800 else None
    if linktype in (101, 228):                       # raw IPv4
        return frame if frame and frame[0] >> 4 == 4 else None
    return None

def dns_name(buf, off):
    labels, jumped, end = [], False, off
    for _ in range(64):
        if off >= len(buf): break
        n = buf[off]
        if n == 0:
            off += 1; break
        if n & 0xC0 == 0xC0:
            if not jumped: end = off + 2
            off, jumped = ((n & 0x3F) << 8) | buf[off + 1], True
            continue
        labels.append(buf[off + 1:off + 1 + n].decode(errors="replace")); off += 1 + n
    return ".".join(labels), (end if jumped else off)

def parse_dns(payload):
    """Return (is_response, qname, [answer IPv4s])."""
    if len(payload) < 12: return None
    flags, qd, an = struct.unpack(">HHH", payload[2:8])
    off, qname = 12, ""
    for _ in range(qd):
        qname, off = dns_name(payload, off); off += 4
    ips = []
    for _ in range(an):
        _, off = dns_name(payload, off)
        if off + 10 > len(payload): break
        rtype, _, _, rdlen = struct.unpack(">HHIH", payload[off:off + 10]); off += 10
        if rtype == 1 and rdlen == 4: ips.append(socket.inet_ntoa(payload[off:off + 4]))
        off += rdlen
    return bool(flags & 0x8000), qname, ips

def tls_sni(payload):
    """Server name from a TLS ClientHello, or None."""
    try:
        if payload[0] != 0x16 or payload[5] != 0x01: return None
        p = 9 + 2 + 32
        p += 1 + payload[p]
        p += 2 + struct.unpack(">H", payload[p:p + 2])[0]
        p += 1 + payload[p]
        end = p + 2 + struct.unpack(">H", payload[p:p + 2])[0]; p += 2
        while p + 4 <= end:
            et, el = struct.unpack(">HH", payload[p:p + 4]); p += 4
            if et == 0:
                return payload[p + 5:p + 5 + struct.unpack(">H", payload[p + 3:p + 5])[0]].decode()
            p += el
    except (IndexError, struct.error, UnicodeDecodeError):
        pass
    return None

# Command names recovered by cheap-shot (docs/protocol.md), for the ones seen towards the cloud.
CMD_NAMES = {6: "GetConnServers", 11: "BigPpiotCmd", 12: "PPMQGetClientID", 13: "PPMQConnect", 17: "PPMQPublish",
             18: "PPMQSubscribe", 20: "PPMQPing", 91: "NatTest1", 92: "NatTest2", 93: "NatProbe", 94: "ReportNat",
             95: "ProbeConfig", 143: "LogAppend", 601: "GetServers", 603: "PPMQDisconnect", 921: "FirmwareCheck",
             931: "FirmwareChanCheck", 1101: "CSCfg", 1103: "CSTokenGet", 2780: "ExecIOTCMD", 11950: "DeviceDataPut"}

def varint(b, i):
    v = s = 0
    while True:
        c = b[i]; i += 1
        v |= (c & 0x7F) << s; s += 7
        if not c & 0x80: return v, i

def pprpc_frames(payload):
    """Yield (cmd, seq, rpc, ciphertext) for PPRPC CTRL frames (UDP ones carry a 'Qp' prefix)."""
    if payload[:2] == b"Qp": payload = payload[2:]
    i = 0
    try:
        while i < len(payload) and payload[i] >> 4 == 4:
            ln, j = varint(payload, i + 1)
            body = payload[j:j + ln]; i = j + ln
            p = 0
            seq, p = varint(body, p); cmd, p = varint(body, p)
            flag = body[p]; p += 1
            if flag & 3 == 1: _, p = varint(body, p)
            yield cmd, seq, flag & 3, body[p:]
    except IndexError:
        return

def pprpc_decrypt(prekey, cmd, seq, rpc, ct):
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    if not ct or len(ct) % 16: return None
    key = hashlib.md5(b"%s,ID:%d-SEQ:%d-RPC:%d" % (prekey, cmd, seq, rpc)).hexdigest().encode()
    pt = Cipher(algorithms.AES(key), modes.CBC(key[:16])).decryptor().update(ct)
    pad = pt[-1]
    return pt[:-pad] if 1 <= pad <= 16 else None

def pb_fields(buf, depth=0):
    """Lenient protobuf decode to a readable string; nested messages are tried when bytes are not text."""
    out, i = [], 0
    try:
        while i < len(buf):
            tag, i = varint(buf, i); f, wt = tag >> 3, tag & 7
            if wt == 0:
                v, i = varint(buf, i); out.append(f"{f}={v}")
            elif wt == 2:
                ln, i = varint(buf, i); v = buf[i:i + ln]; i += ln
                if v and all(32 <= c < 127 for c in v): out.append(f"{f}='{v.decode()}'")
                elif depth < 2 and v: out.append(f"{f}={{{pb_fields(v, depth + 1)}}}")
                else: out.append(f"{f}=<{len(v)} bytes>")
            elif wt == 5: out.append(f"{f}={struct.unpack('<I', buf[i:i + 4])[0]}"); i += 4
            elif wt == 1: out.append(f"{f}={struct.unpack('<Q', buf[i:i + 8])[0]}"); i += 8
            else: break
    except (IndexError, struct.error):
        out.append("…")
    return " ".join(out)

def fmt_bytes(n):
    return f"{n} B" if n < 1024 else f"{n / 1024:.1f} KB"

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pcapng")
    ap.add_argument("--camera", required=True, help="camera IP inside the capture")
    ap.add_argument("--decrypt", action="store_true",
                    help="decrypt PPRPC messages to the cloud with the shared prekey from $A9_PREKEY "
                         "(needs the 'cryptography' package)")
    a = ap.parse_args()
    prekey = None
    if a.decrypt:
        import os
        prekey = os.environ.get("A9_PREKEY", "").encode() or sys.exit("set $A9_PREKEY for --decrypt")

    seen, dns_q, dns_a, sni = set(), collections.Counter(), {}, collections.Counter()
    messages = collections.OrderedDict()
    flows = {}
    t0 = t1 = None
    for ts, lt, frame in read_pcapng(a.pcapng):
        ip = ip_packet(lt, frame)
        if not ip or len(ip) < 20: continue
        ihl, proto = (ip[0] & 15) * 4, ip[9]
        src, dst = socket.inet_ntoa(ip[12:16]), socket.inet_ntoa(ip[16:20])
        total = struct.unpack(">H", ip[2:4])[0]
        key = hashlib.md5(ip[:total]).digest() + int(ts * 10).to_bytes(8, "big")
        if key in seen: continue                     # same packet logged by another pktmon component
        seen.add(key)
        if a.camera not in (src, dst): continue
        t0 = ts if t0 is None else min(t0, ts); t1 = ts if t1 is None else max(t1, ts)
        out = src == a.camera
        remote = dst if out else src
        l4 = ip[ihl:total]
        if proto in (6, 17) and len(l4) >= 8:
            sport, dport = struct.unpack(">HH", l4[:4])
            payload = l4[(l4[12] >> 4) * 4:] if proto == 6 else l4[8:]
            rport = dport if out else sport
        else:
            payload, rport = b"", 0
        pname = {6: "TCP", 17: "UDP", 1: "ICMP"}.get(proto, str(proto))
        if proto == 17 and rport == 53:
            d = parse_dns(payload)
            if d:
                if not d[0]: dns_q[d[1]] += 1
                else: dns_a.setdefault(d[1], set()).update(d[2])
        if proto == 6 and out and payload:
            s = tls_sni(payload)
            if s: sni[s] += 1
        if prekey and payload and not ipaddress.ip_address(remote).is_private:
            for cmd, seq, rpc, ct in pprpc_frames(payload):
                pt = pprpc_decrypt(prekey, cmd, seq, rpc, ct)
                text = pb_fields(pt) if pt is not None else f"<{len(ct)} bytes, not decryptable>"
                m = messages.setdefault((("->" if out else "<-"), pname, remote, rport, cmd, rpc, text),
                                        [0, ts])
                m[0] += 1
        f = flows.setdefault((pname, remote, rport), {"out_p": 0, "out_b": 0, "in_p": 0, "in_b": 0, "times": []})
        f["out_p" if out else "in_p"] += 1
        f["out_b" if out else "in_b"] += len(ip[:total])
        if out: f["times"].append(ts)

    if t0 is None:
        sys.exit(f"no packets to/from {a.camera}")
    ip2name = {ip: n for n, ips in dns_a.items() for ip in ips}
    print(f"Capture span: {t1 - t0:.0f} s, {len(seen)} unique packets\n")
    print("DNS lookups by the camera:")
    for n, c in dns_q.most_common():
        print(f"  {c:4d}x  {n}  ->  {', '.join(sorted(dns_a.get(n, []))) or '(no answer)'}")
    if sni:
        print("\nTLS server names (SNI):")
        for n, c in sni.most_common(): print(f"  {c:4d}x  {n}")
    print("\nRemote endpoints (sorted by bytes sent by the camera):")
    print(f"  {'proto':5} {'remote':15} {'port':>5}  {'sent':>16}  {'received':>16}  {'interval':>9}  name / scope")
    for (pname, remote, rport), f in sorted(flows.items(), key=lambda kv: -kv[1]["out_b"]):
        ts = f["times"]
        gaps = sorted(b - a_ for a_, b in zip(ts, ts[1:]) if b - a_ > 0.5)
        interval = f"~{gaps[len(gaps) // 2]:.0f} s" if gaps else "-"
        scope = "private" if ipaddress.ip_address(remote).is_private else "INTERNET"
        print(f"  {pname:5} {remote:15} {rport:5}  {f['out_p']:5} pk {fmt_bytes(f['out_b']):>8}"
              f"  {f['in_p']:5} pk {fmt_bytes(f['in_b']):>8}  {interval:>9}  {ip2name.get(remote, '')} [{scope}]")
    if prekey:
        print("\nDecrypted PPRPC messages to/from the internet (identical ones grouped):")
        for (d, pname, remote, rport, cmd, rpc, text), (count, first) in messages.items():
            kind = {0: "req", 1: "resp"}.get(rpc, f"rpc{rpc}")
            print(f"  +{first - t0:5.0f}s {count:3d}x {d} {pname} {remote}:{rport}  "
                  f"{cmd} {CMD_NAMES.get(cmd, '?')} ({kind})  {text}")

if __name__ == "__main__":
    main()
