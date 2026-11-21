#!/usr/bin/env python3
"""Measure the host UART/USB path using the Seeed bridge loopback firmware.

The firmware echoes TX payloads as RX frames. This benchmark keeps a bounded
number of transactions outstanding, drains responses on a reader thread, and
reports validated payload and wire throughput in both directions.

No radio transmission occurs. This measures the host serial path only.
"""

import argparse
import json
import struct
import sys
import threading
import time
from pathlib import Path

MAGIC = b"\xA5\x5A"
HELLO, HELLO_ACK, CFG, CFG_ACK, TX, RX, STAT, EVT, PING, PONG = range(1, 11)
MAX_PAYLOAD = 2048


def crc16(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
    return crc


def encode(kind: int, payload: bytes = b"") -> bytes:
    if len(payload) > MAX_PAYLOAD:
        raise ValueError("bridge payload too large")
    body = bytes([kind]) + struct.pack("<H", len(payload)) + payload
    return MAGIC + body + struct.pack("<H", crc16(body))


class Decoder:
    def __init__(self) -> None:
        self.buf = bytearray()

    def push(self, data: bytes):
        self.buf.extend(data)
        frames = []
        while True:
            start = self.buf.find(MAGIC)
            if start < 0:
                # Preserve a trailing first magic byte; the next write may
                # complete it. Discarding it makes split reads depend on USB
                # chunk boundaries.
                if self.buf[-1:] == MAGIC[:1]:
                    del self.buf[:-1]
                else:
                    self.buf.clear()
                return frames
            if start:
                del self.buf[:start]
            if len(self.buf) < 5:
                return frames
            length = struct.unpack_from("<H", self.buf, 3)[0]
            if length > MAX_PAYLOAD:
                del self.buf[0]
                continue
            total = 7 + length
            if len(self.buf) < total:
                return frames
            body = bytes(self.buf[2 : total - 2])
            expected = struct.unpack_from("<H", self.buf, total - 2)[0]
            if crc16(body) != expected:
                del self.buf[0]
                continue
            frames.append((self.buf[2], bytes(self.buf[5 : total - 2])))
            del self.buf[:total]


def stat_payload(payload: bytes):
    if len(payload) != 24:
        return None
    return dict(zip(
        ("tx_packets", "rx_packets", "crc_errors", "drops",
         "tx_timeouts", "resets"),
        struct.unpack("<6I", payload),
    ))


def self_test() -> None:
    payloads = [b"", b"x", bytes(range(255))]
    stream = b"".join(encode(TX, payload) for payload in payloads)
    decoder = Decoder()
    frames = decoder.push(stream[:3]) + decoder.push(stream[3:])
    assert [(kind, payload) for kind, payload in frames] == [
        (TX, payload) for payload in payloads
    ]

    corrupt = bytearray(encode(TX, b"bad"))
    corrupt[-1] ^= 0xFF
    decoder = Decoder()
    assert decoder.push(bytes(corrupt)) == []
    assert decoder.push(encode(PING)) == [(PING, b"")]

    decoder = Decoder()
    split_frames = []
    for byte in stream:
        split_frames.extend(decoder.push(bytes([byte])))
    assert [(kind, payload) for kind, payload in split_frames] == [
        (TX, payload) for payload in payloads
    ]
    print("seeed USB benchmark self-test: PASS")


class Benchmark:
    def __init__(self, port: str, baud: int, window: int, payload_size: int):
        if not 4 <= payload_size <= 255:
            raise ValueError("payload size must be 4..255")
        if not 1 <= window <= 1024:
            raise ValueError("window must be 1..1024")

        # Import only for hardware runs, so --self-test needs no pyserial.
        sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tools"))
        from board_serial import BoardSerial

        self.port = port
        self.baud = baud
        self.window = window
        self.payload_size = payload_size
        self.serial = BoardSerial(
            port, baudrate=baud, timeout=0.05, write_timeout=2, exclusive=True
        )
        self.serial.reset_input_buffer()
        self.serial.reset_output_buffer()

        self.stop = threading.Event()
        self.error = None
        self.lock = threading.Condition()
        self.outstanding = set()
        self.last_progress = time.monotonic()
        self.last_stat = None
        self.rx_payload_bytes = 0
        self.rx_wire_bytes = 0
        self.tx_payload_bytes = 0
        self.tx_wire_bytes = 0
        self.mismatches = 0
        self.unsolicited = 0
        self.reader = threading.Thread(target=self._reader, daemon=True)

    def _close(self) -> None:
        self.serial.close()

    def _reader(self) -> None:
        decoder = Decoder()
        try:
            while not self.stop.is_set():
                waiting = self.serial.in_waiting
                data = self.serial.read(waiting or 1)
                if not data:
                    continue
                with self.lock:
                    self.rx_wire_bytes += len(data)
                for kind, payload in decoder.push(data):
                    if kind == RX and len(payload) >= 6:
                        length = struct.unpack_from("<H", payload, 4)[0]
                        body = payload[6:]
                        if length != len(body) or not 1 <= length <= 255:
                            with self.lock:
                                self.mismatches += 1
                            continue
                        seq = struct.unpack_from("<I", body, 0)[0]
                        with self.lock:
                            if seq not in self.outstanding:
                                self.unsolicited += 1
                                continue
                            self.outstanding.remove(seq)
                            self.rx_payload_bytes += len(body)
                            self.tx_payload_bytes += len(body)
                            self.last_progress = time.monotonic()
                            self.lock.notify_all()
                    elif kind == STAT:
                        parsed = stat_payload(payload)
                        if parsed is not None:
                            with self.lock:
                                self.last_stat = parsed
        except Exception as exc:  # surfaced by the main thread
            self.error = exc
            with self.lock:
                self.stop.set()
                self.lock.notify_all()

    def _wait_hello(self) -> bytes:
        time.sleep(0.5)
        decoder = Decoder()
        old_timeout = self.serial.timeout
        self.serial.timeout = 0.5
        deadline = time.monotonic() + 3.0
        next_send = 0.0
        try:
            while time.monotonic() < deadline:
                now = time.monotonic()
                if now >= next_send:
                    self.serial.write(encode(HELLO, b"\x01"))
                    self.serial.flush()
                    next_send = now + 0.25
                data = self.serial.read(max(1, self.serial.in_waiting))
                if not data:
                    continue
                for kind, payload in decoder.push(data):
                    if kind == HELLO_ACK:
                        if len(payload) != 8:
                            raise RuntimeError("malformed HELLO_ACK")
                        return payload
        finally:
            self.serial.timeout = old_timeout
        raise RuntimeError("no HELLO_ACK; is loopback firmware flashed?")

    def run(self, seconds: float):
        ack = self._wait_hello()
        protocol, fw_major, fw_minor, fw_patch, chip, caps = struct.unpack(
            "<BBBBHH", ack
        )
        caps = struct.unpack("<H", ack[6:8])[0]
        if protocol != 1 or chip != 0 or caps != 0x0008:
            raise RuntimeError(
                f"unexpected loopback identity: protocol={protocol} chip={chip} "
                f"caps=0x{caps:04x}"
            )

        self.reader.start()
        seq = 0
        start = None
        send_end = None
        end = None
        write_errors = 0
        deadline = time.monotonic() + seconds
        self.last_progress = time.monotonic()
        try:
            while time.monotonic() < deadline:
                with self.lock:
                    while len(self.outstanding) >= self.window:
                        if self.error or self.stop.is_set():
                            raise RuntimeError(f"reader failed: {self.error}")
                        if time.monotonic() - self.last_progress > 3.0:
                            raise RuntimeError(
                                f"no loopback response for 3s; "
                                f"outstanding={len(self.outstanding)} "
                                f"stat={self.last_stat}"
                            )
                        self.lock.wait(0.25)
                body = struct.pack("<I", seq) + bytes(
                    (i * 17 + seq) & 0xFF for i in range(self.payload_size - 4)
                )
                frame = encode(TX, body)
                with self.lock:
                    self.outstanding.add(seq)
                    self.tx_wire_bytes += len(frame)
                try:
                    self.serial.write(frame)
                    self.serial.flush()
                except Exception:
                    with self.lock:
                        self.outstanding.discard(seq)
                        self.tx_wire_bytes -= len(frame)
                    write_errors += 1
                    break
                if start is None:
                    start = time.monotonic()
                seq += 1
            send_end = time.monotonic()

            # Let the bounded window drain before taking the final sample.
            drain_deadline = time.monotonic() + 3.0
            with self.lock:
                while self.outstanding and time.monotonic() < drain_deadline:
                    self.lock.wait(0.2)
                end = max(send_end, self.last_progress)
                losses = len(self.outstanding)
                self.outstanding.clear()
        finally:
            self.stop.set()
            self.reader.join(timeout=2.0)

        if start is None:
            raise RuntimeError("no frames were sent")
        elapsed = max(end - start, 1e-9)
        with self.lock:
            result = {
                "port": self.port,
                "baud": self.baud,
                "payload_size": self.payload_size,
                "window": self.window,
                "seconds": round(elapsed, 6),
                "frames_sent": seq,
                "frames_echoed": seq - write_errors - losses,
                "losses": losses,
                "write_errors": write_errors,
                "mismatches": self.mismatches,
                "unsolicited": self.unsolicited,
                "host_to_device_payload_kbit_s": round(
                    self.tx_payload_bytes * 8 / elapsed / 1000, 3
                ),
                "device_to_host_payload_kbit_s": round(
                    self.rx_payload_bytes * 8 / elapsed / 1000, 3
                ),
                "host_to_device_wire_kbit_s": round(
                    self.tx_wire_bytes * 8 / elapsed / 1000, 3
                ),
                "device_to_host_wire_kbit_s": round(
                    self.rx_wire_bytes * 8 / elapsed / 1000, 3
                ),
                "device_stat": self.last_stat,
            }
        self._close()
        return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", help="Serial device, preferably /dev/serial/by-id/...")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--seconds", type=float, default=5.0)
    parser.add_argument("--payload-size", type=int, default=255)
    parser.add_argument("--window", type=int, default=4)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if not args.self_test and not args.port:
        parser.error("--port is required for a hardware run")
    if args.seconds <= 0:
        parser.error("--seconds must be positive")
    return args


def main() -> int:
    args = parse_args()
    if args.self_test:
        self_test()
        return 0

    try:
        result = Benchmark(
            args.port, args.baud, args.window, args.payload_size
        ).run(args.seconds)
    except Exception as exc:
        print(f"seeed USB benchmark: FAIL: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2, sort_keys=True))
    loss_pct = 100.0 * result["losses"] / max(1, result["frames_sent"])
    failed = (
        result["frames_sent"] == 0
        or result["mismatches"]
        or result["write_errors"]
        or loss_pct > 1.0
    )
    print(
        f"seeed USB benchmark: {'FAIL' if failed else 'PASS'} "
        f"(loss={result['losses']}/{result['frames_sent']} = {loss_pct:.2f}%)"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
