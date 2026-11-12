#!/usr/bin/env python3
"""Extract individual members of the OpenFLRC v1.0 Zenodo archive without downloading 4.9 GB.

The archive is a single 4.94 GB ZIP64 file that is almost entirely video. The file listing lives at
the END of a zip, so two HTTP range requests give the whole structure; each member then costs one
30-byte local-header fetch plus only that member's compressed bytes.

Why ZIP64 matters: the central-directory offset in the normal End-Of-Central-Directory record is
0xFFFFFFFF for a >4 GB archive. The real value is in the ZIP64 EOCD record, which is found via the
ZIP64 EOCD locator sitting immediately before the normal EOCD. Reading the normal EOCD alone gives
offset 4294967295 and a zero-entry listing -- which is what happened the first time this was tried.

Usage:
    python3 zenodo_extract.py --list
    python3 zenodo_extract.py --get README.md 'firmware\\libraries\\OpenFLRC_Library\\src\\OpenFLRC.cpp'

Members are written into the current directory under their base name.
"""
import argparse
import os
import struct
import subprocess
import sys
import zlib

RECORD = "21159006"
ZIPNAME = "OpenFLRC_v1.0_Hardware_and_Data.zip"
URL = "https://zenodo.org/records/%s/files/%s?download=1" % (RECORD, ZIPNAME)

# DO NOT send a browser User-Agent here. Measured: with a Chrome UA string the CDN returns 763 bytes
# for a 65536-byte range request (EOCD absent); without it the same range returns all 65536 bytes with
# the EOCD present. A browser UA makes the CDN take a different path that mishandles Range.
# This was the cause of "no End-Of-Central-Directory found" -- three debugging rounds, and the
# archive was never the problem.


def fetch(offset, length, timeout=240):
    """Fetch a byte range.

    Uses --location with a redirect chain: zenodo.org 302s to a CDN, and a range request against the
    pre-redirect URL can come back as a full-body 200. Checking the returned length against the
    requested length is the only reliable way to know the range was honoured.
    """
    r = subprocess.run(
        ["curl", "-sL", "--max-time", str(timeout),
         "-r", "%d-%d" % (offset, offset + length - 1), URL],
        capture_output=True)
    return r.stdout


def total_size():
    r = subprocess.run(["curl", "-sIL", "--max-time", "60", URL],
                       capture_output=True, text=True)
    for line in r.stdout.splitlines():
        if line.lower().startswith("content-length:"):
            return int(line.split(":")[1].strip())
    raise SystemExit("could not read Content-Length")


def build_index():
    size = total_size()
    tail_len = min(65536, size)
    tail = fetch(size - tail_len, tail_len)

    j = tail.rfind(b"PK\x05\x06")
    if j < 0:
        raise SystemExit("no End-Of-Central-Directory found")
    eocd = tail[j:j + 22]
    _, _, _, _, n_entries, cd_size, cd_off, _ = struct.unpack("<IHHHHIIH", eocd)

    if cd_off == 0xFFFFFFFF or cd_size == 0xFFFFFFFF or n_entries == 0xFFFF:
        # ZIP64: the locator precedes the normal EOCD and points at the ZIP64 EOCD record.
        k = tail.rfind(b"PK\x06\x07")
        if k < 0:
            raise SystemExit("ZIP64 locator not found")
        _, _, z64_off, _ = struct.unpack("<IIQI", tail[k:k + 20])
        z64 = fetch(z64_off, 56)
        n_entries, cd_size, cd_off = struct.unpack("<QQQ", z64[32:56])

    cd = fetch(cd_off, cd_size)
    index = {}
    pos = 0
    while pos < len(cd) and cd[pos:pos + 4] == b"PK\x01\x02":
        hdr = struct.unpack("<IHHHHHHIIIHHHHHII", cd[pos:pos + 46])
        method, csize, usize = hdr[4], hdr[8], hdr[9]
        nlen, elen, clen, local_off = hdr[10], hdr[11], hdr[12], hdr[16]
        name = cd[pos + 46:pos + 46 + nlen].decode("utf-8", "replace")
        extra = cd[pos + 46 + nlen:pos + 46 + nlen + elen]

        # ZIP64 extended information: present only for fields set to 0xFFFFFFFF, in fixed order.
        if usize == 0xFFFFFFFF or csize == 0xFFFFFFFF or local_off == 0xFFFFFFFF:
            p = 0
            while p + 4 <= len(extra):
                tag, ln = struct.unpack("<HH", extra[p:p + 4])
                body = extra[p + 4:p + 4 + ln]
                if tag == 0x0001:
                    q = 0
                    if usize == 0xFFFFFFFF:
                        usize = struct.unpack("<Q", body[q:q + 8])[0]
                        q += 8
                    if csize == 0xFFFFFFFF:
                        csize = struct.unpack("<Q", body[q:q + 8])[0]
                        q += 8
                    if local_off == 0xFFFFFFFF:
                        local_off = struct.unpack("<Q", body[q:q + 8])[0]
                        q += 8
                p += 4 + ln

        index[name] = (method, csize, usize, local_off)
        pos += 46 + nlen + elen + clen
    return index


def get(index, zname, out=None):
    if zname not in index:
        print("MISS %s" % zname)
        return False
    method, csize, usize, local_off = index[zname]
    lh = fetch(local_off, 30)
    nlen, elen = struct.unpack("<HH", lh[26:30])
    data_off = local_off + 30 + nlen + elen
    blob = fetch(data_off, csize)
    if len(blob) != csize:
        print("SHORT %s: %d of %d bytes" % (zname, len(blob), csize))
        return False
    raw = zlib.decompress(blob, -15) if method == 8 else blob
    if len(raw) != usize:
        print("WARN %s: decompressed %d, expected %d" % (zname, len(raw), usize))
    out = out or os.path.basename(zname.replace("\\", "/"))
    with open(out, "wb") as fh:
        fh.write(raw)
    print("OK   %-58s -> %-30s %8d bytes" % (zname, out, len(raw)))
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="print every member")
    ap.add_argument("--get", nargs="+", metavar="MEMBER", help="extract these members")
    a = ap.parse_args()
    if not a.list and not a.get:
        ap.error("give --list or --get")
    index = build_index()
    if a.list:
        print("%d members\n" % len(index))
        for name, (method, csize, usize, off) in sorted(index.items()):
            print("  %-92s %10.1f KB" % (name[:92], usize / 1024))
    if a.get:
        ok = sum(get(index, m) for m in a.get)
        print("\n%d of %d extracted" % (ok, len(a.get)))
        return 0 if ok == len(a.get) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
