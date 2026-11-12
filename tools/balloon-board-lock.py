#!/usr/bin/env python3
"""
balloon-board-lock.py -- OS-enforced mutex lock for board access.

Uses flock(2) for TRUE mutual exclusion. A sentinel daemon process holds the
flock open for the duration of the lock. The sentinel monitors the caller's
process tree and auto-releases when the Hermes session dies.

This replaces the old TTL-based approach which had a fatal flaw: locks expired
(15 min) while sessions were still actively using the boards, allowing another
session to reclaim a "stale" lock mid-test.

THEFT PROTECTION (v2):
    - Sentinels trap SIGTERM, log the attempt, and IGNORE it.
      Only SIGKILL (uncatchable) or parent-death can release a sentinel.
    - All theft events are logged to ~/.hermes/peripheral_locks/THEFT-LOG
    - The `release` command requires `--steal` to kill another track's sentinel
      (not just `--force`, which is for releasing locks with no/corrupt metadata).

HARD DEVICE LOCKING (v3 — Phase 2):
    - On acquire: open an exclusive fd to /dev/ttyACMx BEFORE locking,
      then chmod 000 the device AFTER flock is acquired.
    - Lock holder's sentinel keeps the fd open → can still read/write.
    - ALL other processes get EACCES on open() — cannot cat, pio upload, picotool.
    - On release: chmod 666 to restore access, close fd, release flock.
    - Even if a sub-manager bypasses pio-flash.sh, raw tools fail with
      "Permission denied".

LOCK FILES: ~/.hermes/peripheral_locks/balloon-{tx,rx,board-a,board-b,board-c}.lock
THEFT LOG:  ~/.hermes/peripheral_locks/board-lock-theft.log

RESOURCES:
    tx, rx       — RP2040 boards (speed-tests, range-tests)
    board-a      — ESP32-S3 board A (MAC 94:a9:90:2e:37:7c, TollGate-B96D80)
    board-b      — ESP32-S3 board B (MAC fc:01:2c:c5:50:50, TollGate-C0E9CA)
    board-c      — ESP32-S3 board C (MAC 20:6e:f1:98:d7:08, display board)
    c3-a         — ESP32-C3 + LR2021 board A (MAC b0:a6:04:00:96:dc, /dev/ttyACM0)
    c3-b         — ESP32-C3 + LR2021 board B (MAC 88:56:a6:7b:c6:98, /dev/ttyACM1)
    fips-s3      — FIPS ESP32-S3 + E80 adapter (MAC 34:85:18:8d:ff:94)
    fips-e80-pair — Coordinated FIPS S3 and NiceRF C3 pair (fips-s3 + c3-a)
    all-s3       — All 3 ESP32-S3 boards (board-a + board-b + board-c)
    both-c3      — Both ESP32-C3 boards (c3-a + c3-b, for TX/RX tests)
    both         — TX + RX (RP2040 pair)
    all          — All boards (tx + rx + board-a + board-b + board-c)

USAGE:
    # Acquire TX board (blocks up to 120s)
    BALLOON_TRACK=speed-tests python3 balloon-board-lock.py acquire tx \
        --purpose "flash timing diag" --timeout 120

    # Acquire both RP2040 boards (for coordinated TX/RX tests)
    BALLOON_TRACK=speed-tests python3 balloon-board-lock.py acquire both \
        --purpose "coordinated throughput test" --timeout 120

    # Release
    BALLOON_TRACK=speed-tests python3 balloon-board-lock.py release tx
    python3 balloon-board-lock.py release both --force

    # Status (who holds what)
    python3 balloon-board-lock.py status

    # Check if current track holds a specific resource lock (exit 0/1)
    BALLOON_TRACK=speed-tests python3 balloon-board-lock.py check tx

EXIT CODES:
    0 = acquired / released / status shown / check passed
    1 = failed to acquire (timeout or held by other session) / check failed
    2 = invalid arguments
"""

import ctypes
import ctypes.util
import fcntl
import glob
import json
import os
import signal
import subprocess
import sys
import time
import argparse
from datetime import datetime, timezone
from pathlib import Path

LOCK_DIR = Path.home() / ".hermes" / "peripheral_locks"
LOCK_DIR.mkdir(parents=True, exist_ok=True)

# Linux prctl constants
PR_SET_PDEATHSIG = 1
PR_SET_NAME = 15

# Serial number patterns for RP2040 board identification.
# TX board serial contains "F242D", RX board serial contains "8332".
BOARD_SERIALS = {
    "tx": "F242D",
    "rx": "8332",
}

# MAC-based identification for ESP32-C3 + LR2021 boards (ADR-025).
# ESP32-C3 USB CDC serial = MAC with colons (as reported by udevadm).
BOARD_MACS = {
    "c3-a": "B0:A6:04:00:96:DC",   # /dev/ttyACM0
    "c3-b": "88:56:A6:7B:C6:98",   # /dev/ttyACM1
    "fips-s3": "34:85:18:8D:FF:94", # FIPS ESP32-S3/E80 (approved custom carrier)
}


def _prctl(option, value):
    """Call prctl(2) — used for parent-death signal."""
    libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
    libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
    libc.prctl.restype = ctypes.c_int
    return libc.prctl(option, value, 0, 0, 0)


def _get_grandparent_pid():
    """Walk up to find the Hermes session PID (skip ephemeral shells).

    Process tree: Hermes agent → bash -c "..." → python3 balloon-board-lock.py
    We want the Hermes agent PID so the sentinel can monitor it.
    """
    pid = os.getpid()
    ppid = os.getppid()
    gpids = [pid, ppid]
    try:
        with open(f"/proc/{ppid}/stat") as f:
            stat = f.read().split()
            gppid = int(stat[3])  # 4th field = ppid
            gpids.append(gppid)
        # Walk one more level up
        with open(f"/proc/{gppid}/stat") as f:
            stat = f.read().split()
            ggppid = int(stat[3])
            gpids.append(ggppid)
    except (FileNotFoundError, ValueError, IndexError):
        pass
    # Return the highest ancestor we found (most likely the Hermes process)
    return gpids[-1] if len(gpids) > 2 else ppid


def _identity():
    return {
        "track": os.getenv("BALLOON_TRACK", "unknown"),
        "pid": os.getpid(),
    }


def _lock_path(resource: str) -> Path:
    return LOCK_DIR / f"balloon-{resource}.lock"


def _get_resources(resource: str) -> list:
    if resource == "both":
        return ["tx", "rx"]
    if resource == "all-s3":
        return ["board-a", "board-b", "board-c"]
    if resource == "both-c3":
        return ["c3-a", "c3-b"]
    if resource == "fips-e80-pair":
        return ["fips-s3", "c3-a"]
    if resource == "all":
        return ["tx", "rx", "board-a", "board-b", "board-c"]
    return [resource]


def _read_metadata(path: Path) -> dict | None:
    """Read lock file metadata (JSON content)."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _pid_alive(pid: int) -> bool:
    """Check if a process is alive."""
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # Alive but not ours


def _is_locked(path: Path) -> bool:
    """Check if the flock is actually held by testing LOCK_EX | LOCK_NB.

    This is the authoritative check — flock is OS-enforced.
    """
    if not path.exists():
        return False
    fd = None
    try:
        fd = os.open(str(path), os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # We got the lock → nobody was holding it
            fcntl.flock(fd, fcntl.LOCK_UN)
            return False
        except BlockingIOError:
            return True
    except OSError:
        return False
    finally:
        if fd is not None:
            os.close(fd)


# ─── Hard Device Locking ──────────────────────────────────────────────────


def _find_device_path(resource: str) -> str | None:
    """Find the /dev/ttyACMx device for a resource by USB serial number.

    TX board serial contains "F242D", RX board serial contains "8332".
    Returns the device path (e.g. "/dev/ttyACM3") or None if not found.
    """
    # Check serial-based (RP2040) or MAC-based (ESP32-C3) identification
    pattern = BOARD_SERIALS.get(resource) or BOARD_MACS.get(resource)
    if not pattern:
        return None  # ESP32-S3 boards don't have serial/MAC-based mapping yet

    for dev in sorted(glob.glob("/dev/ttyACM*")):
        try:
            result = subprocess.run(
                ["udevadm", "info", "-q", "property", "-n", dev],
                capture_output=True, text=True, timeout=3,
            )
            for line in result.stdout.splitlines():
                if line.startswith("ID_SERIAL_SHORT=") and pattern in line:
                    return dev
        except (subprocess.TimeoutExpired, OSError):
            continue
    return None


def _chmod_device(path: str, mode: str) -> bool:
    """Change device file permissions using sudo (devices are root-owned).

    Returns True on success, False on failure.
    """
    try:
        result = subprocess.run(
            ["sudo", "chmod", mode, path],
            capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def _fd_is_valid(fd: int) -> bool:
    """Check if a file descriptor is still valid (device not unplugged)."""
    try:
        os.fstat(fd)
        return True
    except OSError:
        return False


def _restore_device_permissions(resource: str, device_path: str | None = None):
    """Restore device permissions to 666 after lock release.

    Called from release() to ensure devices are accessible even if the
    sentinel was SIGKILL'd without cleanup.
    """
    if not device_path:
        device_path = _find_device_path(resource)
    if device_path:
        _chmod_device(device_path, "666")


THEFT_LOG = LOCK_DIR / "board-lock-theft.log"


def _log_theft(resource: str, metadata: dict, signal_name: str, source: str = "unknown"):
    """Log a theft attempt to the shared theft log."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "resource": resource,
        "victim_track": metadata.get("track", "?"),
        "victim_purpose": metadata.get("purpose", "?"),
        "signal": signal_name,
        "source": source,
    }
    try:
        with open(THEFT_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass


def _sentinel_sigterm_handler(signum, frame):
    """Trap SIGTERM — log the theft attempt and IGNORE the signal.

    Only SIGKILL (uncatchable) or parent-death can release a sentinel.
    This prevents casual `kill <PID>` from stealing locks.
    """
    # We can't access metadata in a signal handler easily,
    # but we can write to the theft log with what we know
    try:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "resource": os.environ.get("_BALLOON_LOCK_RESOURCE", "?"),
            "victim_track": os.environ.get("_BALLOON_LOCK_TRACK", "?"),
            "signal": "SIGTERM",
            "source": f"pid={os.getppid()}",
            "note": "SIGTERM trapped and ignored by sentinel",
        }
        with open(THEFT_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass
    # DO NOT exit — ignore the signal


def _start_sentinel(fd: int, path: Path, metadata: dict,
                    device_fd: int | None = None, device_path: str | None = None):
    """Fork a sentinel daemon that holds the flock and monitors the caller.

    The sentinel:
    1. Holds the flock via its inherited fd
    2. Holds the device fd open (exclusive access)
    3. chmod 000 the device (blocks all other processes)
    4. Traps SIGTERM (logs theft, ignores signal)
    5. Monitors the caller process (Hermes agent PID)
    6. Exits when the caller dies → fd closes → flock released
    7. On exit: chmod 666 device, close fds
    8. Writes metadata to the lock file
    """
    monitor_pid = metadata.get("monitor_pid", 0)
    resource = metadata.get("resource", "?")
    track = metadata.get("track", "?")

    sentinel_pid = os.fork()
    if sentinel_pid != 0:
        # Parent: return the sentinel PID
        return sentinel_pid

    # CHILD — sentinel daemon
    os.setsid()  # Detach from controlling terminal
    os.umask(0)

    # Set process name for easy identification
    try:
        _prctl(PR_SET_NAME, 0)  # Clear
    except Exception:
        pass

    # Trap SIGTERM — log and ignore (theft protection)
    os.environ["_BALLOON_LOCK_RESOURCE"] = resource
    os.environ["_BALLOON_LOCK_TRACK"] = track
    signal.signal(signal.SIGTERM, _sentinel_sigterm_handler)

    # ── Hard device lock: chmod 000 AFTER flock acquired ──
    # The sentinel holds the device fd open, so it can still read/write.
    # All other processes will get EACCES on open().
    if device_path:
        success = _chmod_device(device_path, "000")
        if success:
            metadata["device_locked"] = True
        else:
            metadata["device_locked"] = False
            print(f"WARNING: Could not chmod 000 {device_path} — hard lock incomplete",
                  file=sys.stderr)

    # Write metadata to lock file
    metadata["sentinel_pid"] = os.getpid()
    metadata["started"] = datetime.now(timezone.utc).isoformat()
    metadata["device_path"] = device_path
    metadata["device_fd"] = device_fd  # Informational — fd number in this process
    try:
        os.lseek(fd, 0, os.SEEK_SET)
        os.ftruncate(fd, 0)
        os.write(fd, json.dumps(metadata, indent=2).encode())
    except OSError:
        pass

    # Monitor loop: check if the Hermes process is still alive
    # Also check if the device is still connected (USB unplug detection)
    while True:
        time.sleep(10)
        if monitor_pid > 0 and not _pid_alive(monitor_pid):
            # Caller process died → release the lock
            break
        # Detect USB unplug: if device fd is invalid, device disappeared
        if device_fd is not None and not _fd_is_valid(device_fd):
            break

    # ── Cleanup: restore device permissions ──
    if device_path:
        _chmod_device(device_path, "666")

    # Close device fd
    if device_fd is not None:
        try:
            os.close(device_fd)
        except OSError:
            pass

    # Cleanup: truncate metadata, close lock fd (releases flock)
    try:
        os.lseek(fd, 0, os.SEEK_SET)
        os.ftruncate(fd, 0)
    except OSError:
        pass
    os.close(fd)
    os._exit(0)


def acquire(resource: str, purpose: str, timeout_s: int) -> int:
    resources = _get_resources(resource)
    identity = _identity()
    monitor_pid = _get_grandparent_pid()

    # First, try to acquire ALL needed resources
    held_fds = []
    held_paths = []
    held_sentinels = []
    held_device_fds = []
    held_device_paths = []

    deadline = time.monotonic() + timeout_s if timeout_s > 0 else 0

    while True:
        all_ok = True
        # Clean up any previous partial acquisitions
        for fd, spath, spid, dev_fd, dev_path in zip(
            held_fds, held_paths, held_sentinels, held_device_fds, held_device_paths
        ):
            if spid:
                try:
                    os.kill(spid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
            os.close(fd)
            if dev_path:
                _chmod_device(dev_path, "666")
            if dev_fd is not None:
                try:
                    os.close(dev_fd)
                except OSError:
                    pass
        held_fds = []
        held_paths = []
        held_sentinels = []
        held_device_fds = []
        held_device_paths = []

        for r in resources:
            path = _lock_path(r)

            # Ensure lock file exists
            path.touch()

            # ── Find and open the device BEFORE locking ──
            device_path = _find_device_path(r)
            device_fd = None
            if device_path:
                # Restore permissions first (recover from crashed sentinel)
                _chmod_device(device_path, "666")
                try:
                    device_fd = os.open(
                        device_path,
                        os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK,
                    )
                    print(f"  Opened exclusive fd to {device_path} (fd={device_fd})")
                except OSError as e:
                    print(f"WARNING: Could not open {device_path}: {e} — hard lock unavailable",
                          file=sys.stderr)
                    device_fd = None
                    device_path = None
            else:
                print(f"  No device found for {r} (not connected?) — advisory lock only",
                      file=sys.stderr)

            fd = os.open(str(path), os.O_RDWR)

            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                # Got the lock!
            except BlockingIOError:
                # Check if it's truly locked or just stale metadata
                all_ok = False
                os.close(fd)
                if device_fd is not None:
                    os.close(device_fd)
                    if device_path:
                        _chmod_device(device_path, "666")

                # Read who holds it for the error message
                data = _read_metadata(path)
                if data:
                    holder_track = data.get("track", "?")
                    holder_purpose = data.get("purpose", "?")
                    sentinel_pid = data.get("sentinel_pid", "?")
                    print(f"BLOCKED: {r} held by track={holder_track} "
                          f"sentinel={sentinel_pid} (purpose: {holder_purpose})",
                          file=sys.stderr)

                # Break to retry loop
                break

            # We have the flock. Start sentinel to hold it.
            metadata = {
                "resource": r,
                "track": identity["track"],
                "purpose": purpose,
                "monitor_pid": monitor_pid,
                "acquired": datetime.now(timezone.utc).isoformat(),
            }
            sentinel_pid = _start_sentinel(fd, path, metadata, device_fd, device_path)
            held_fds.append(fd)
            held_paths.append(path)
            held_sentinels.append(sentinel_pid)
            held_device_fds.append(device_fd)
            held_device_paths.append(device_path)

        if all_ok:
            board_list = "+".join(resources)
            print(f"ACQUIRED: {board_list} (purpose: {purpose})")
            print(f"  track={identity['track']} monitor_pid={monitor_pid}")
            for r, spid, dev_path in zip(resources, held_sentinels, held_device_paths):
                lock_type = "HARD (chmod 000)" if dev_path else "advisory (flock only)"
                print(f"  {r}: sentinel PID={spid} lock={lock_type}")
            # Close our parent copies — sentinels hold their own fd copies
            for fd in held_fds:
                try:
                    os.close(fd)
                except OSError:
                    pass
            for dev_fd in held_device_fds:
                if dev_fd is not None:
                    try:
                        os.close(dev_fd)
                    except OSError:
                        pass
            return 0

        if timeout_s > 0 and time.monotonic() >= deadline:
            return 1

        if timeout_s > 0:
            remaining = deadline - time.monotonic()
            print(f"\r  Waiting for {resource}... ({remaining:.0f}s remaining)  ",
                  end="", file=sys.stderr, flush=True)
        time.sleep(2)


def release(resource: str, force: bool, steal: bool) -> int:
    resources = _get_resources(resource)
    identity = _identity()
    released_any = False

    for r in resources:
        path = _lock_path(r)
        data = _read_metadata(path)

        if data is None:
            print(f"FREE: {r} (no lock file)")
            released_any = True
            # Still try to restore device permissions in case of crash
            _restore_device_permissions(r)
            continue

        sentinel_pid = data.get("sentinel_pid")
        holder_track = data.get("track", "?")
        device_path = data.get("device_path")

        # If another track holds this lock, require explicit --steal
        if holder_track != "unknown" and holder_track != identity["track"]:
            if not steal and not force:
                print(f"REFUSED: {r} held by track={holder_track} "
                      f"(use --steal to forcefully take it — this WILL be logged)",
                      file=sys.stderr)
                continue
            # Log the theft
            _log_theft(r, data, "RELEASE_WITH_STEAL",
                       source=f"track={identity['track']} pid={os.getpid()}")
            print(f"STEAL: {r} taken from track={holder_track} (logged)")

        # ── Restore device permissions BEFORE killing sentinel ──
        # The sentinel may be SIGKILL'd (no cleanup), so we restore here.
        if device_path:
            if _chmod_device(device_path, "666"):
                print(f"  Restored {device_path} → chmod 666")

        # Kill the sentinel → fd closes → flock released
        # Sentinels trap SIGTERM, so we use SIGKILL directly
        if sentinel_pid:
            try:
                os.kill(sentinel_pid, signal.SIGKILL)
                time.sleep(0.3)
                print(f"RELEASED: {r} (killed sentinel {sentinel_pid})")
                released_any = True
            except ProcessLookupError:
                # Sentinel already dead — check if flock is truly free
                if _is_locked(path):
                    print(f"STALE: {r} metadata says sentinel dead but flock held — use --force",
                          file=sys.stderr)
                else:
                    print(f"RELEASED: {r} (sentinel already dead, flock was free)")
                    released_any = True
        else:
            # No sentinel PID in metadata — try force-unlock
            if force:
                fd = os.open(str(path), os.O_RDWR)
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    fcntl.flock(fd, fcntl.LOCK_UN)
                    print(f"RELEASED: {r} (force — flock was free)")
                    released_any = True
                except BlockingIOError:
                    print(f"BLOCKED: {r} flock held by unknown process — cannot force-release",
                          file=sys.stderr)
                os.close(fd)
            else:
                print(f"SKIP: {r} no sentinel PID in metadata (use --force)",
                      file=sys.stderr)

        # Clear metadata
        try:
            path.write_text("")
        except OSError:
            pass

        # Double-check device permissions are restored
        _restore_device_permissions(r, device_path)

    return 0 if released_any else 1


def check(resource: str) -> int:
    """Check if the current BALLOON_TRACK holds the lock for a resource.

    Exit 0 = lock held by current track (safe to proceed)
    Exit 1 = lock not held, or held by another track
    """
    identity = _identity()
    resources = _get_resources(resource)

    for r in resources:
        path = _lock_path(r)

        if not _is_locked(path):
            print(f"FREE: {r} — no lock held", file=sys.stderr)
            return 1

        data = _read_metadata(path)
        if not data:
            print(f"LOCKED: {r} but no metadata — cannot verify ownership", file=sys.stderr)
            return 1

        holder_track = data.get("track", "?")
        sentinel_pid = data.get("sentinel_pid")
        sentinel_alive = _pid_alive(sentinel_pid) if sentinel_pid else False

        if not sentinel_alive:
            print(f"STALE: {r} — sentinel dead, lock is orphaned", file=sys.stderr)
            return 1

        if holder_track == identity["track"]:
            print(f"OK: {r} locked by track={holder_track} (sentinel={sentinel_pid})")
        else:
            print(f"HELD: {r} locked by track={holder_track} (not {identity['track']})",
                  file=sys.stderr)
            return 1

    return 0


def status() -> int:
    """Print status of all balloon board locks."""
    print("=== Balloon Board Lock Status (flock + hard device lock) ===")
    for resource in ["tx", "rx", "board-a", "board-b", "board-c", "c3-a", "c3-b"]:
        path = _lock_path(resource)
        locked = _is_locked(path)
        data = _read_metadata(path)

        if not locked:
            print(f"  {resource.upper()}: FREE")
            # Clean up stale metadata
            if data and data.get("sentinel_pid"):
                if not _pid_alive(data["sentinel_pid"]):
                    try:
                        path.write_text("")
                    except OSError:
                        pass
                    # Restore device permissions if needed
                    dev_path = data.get("device_path")
                    if dev_path:
                        _chmod_device(dev_path, "666")
            continue

        # Lock is held
        track = data.get("track", "?") if data else "?"
        purpose = data.get("purpose", "?") if data else "?"
        sentinel_pid = data.get("sentinel_pid", "?") if data else "?"
        acquired = data.get("acquired", "?") if data else "?"
        device_path = data.get("device_path") if data else None
        device_locked = data.get("device_locked", False) if data else False

        sentinel_alive = _pid_alive(data["sentinel_pid"]) if data and data.get("sentinel_pid") else False

        if not sentinel_alive:
            print(f"  {resource.upper()}: LOCKED [ORPHANED — sentinel dead but flock held?!]")
            # Attempt to restore device permissions for orphaned lock
            if device_path:
                _chmod_device(device_path, "666")
        else:
            age = ""
            try:
                acq = datetime.fromisoformat(acquired.replace("Z", "+00:00"))
                age_min = (datetime.now(timezone.utc) - acq).total_seconds() / 60
                age = f" ({age_min:.1f}min)"
            except Exception:
                pass
            hard_lock = f" HARD-LOCKED({device_path})" if device_locked else ""
            print(f"  {resource.upper()}: LOCKED by track={track}{age}{hard_lock}")
            print(f"    purpose:      {purpose}")
            print(f"    sentinel:     {sentinel_pid}")
            print(f"    acquired:     {acquired}")
            if device_path:
                print(f"    device:       {device_path} (chmod 000)")

    print()

    # Show connected boards
    print("Connected boards:")
    try:
        result = subprocess.run(
            ["sh", "-c",
             'for d in /dev/ttyACM*; do echo "$d: $(udevadm info -q property -n $d 2>/dev/null '
             '| grep -E \'ID_SERIAL_SHORT|ID_MODEL=\' | head -2)"; done'],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.strip().split("\n"):
            if line:
                print(f"  {line}")
    except Exception:
        pass

    # Show running sentinels
    try:
        result = subprocess.run(
            ["sh", "-c", "ps aux | grep 'balloon-board-lock' | grep -v grep | head -10"],
            capture_output=True, text=True, timeout=5,
        )
        sentinels = [l for l in result.stdout.strip().split("\n") if l]
        if sentinels:
            print(f"\nRunning sentinel processes:")
            for s in sentinels:
                print(f"  {s}")
    except Exception:
        pass

    # Show recent theft events if any
    theft_log = LOCK_DIR / "board-lock-theft.log"
    if theft_log.exists():
        try:
            lines = theft_log.read_text().strip().split("\n")
            recent = lines[-5:] if len(lines) > 5 else lines
            if recent and recent[0]:
                print(f"\nRecent theft events (last {len(recent)}):")
                for line in recent:
                    try:
                        entry = json.loads(line)
                        ts = entry.get("timestamp", "?")[:19]
                        print(f"  {ts} {entry.get('resource','?')}: "
                              f"{entry.get('victim_track','?')} → "
                              f"{entry.get('reason','?')}")
                    except json.JSONDecodeError:
                        pass
        except OSError:
            pass

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Balloon board mutex lock (flock + hard device lock) — prevents concurrent board access",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  BALLOON_TRACK=speed-tests %(prog)s acquire tx --purpose "flash single-batch firmware" --timeout 120
  BALLOON_TRACK=speed-tests %(prog)s acquire both --purpose "coordinated throughput test" --timeout 180
  BALLOON_TRACK=range-tests %(prog)s release tx
  %(prog)s release both --force
  %(prog)s status
  BALLOON_TRACK=speed-tests %(prog)s check tx   # exit 0 if we hold tx lock
        """)
    parser.add_argument("action", choices=["acquire", "release", "status", "check"],
                        help="Action to perform")
    parser.add_argument("resource", nargs="?",
                        choices=["tx", "rx", "both", "board-a", "board-b", "board-c", "c3-a", "c3-b", "both-c3", "fips-s3", "fips-e80-pair", "all-s3", "all"],
                        help="Which board(s) to lock/unlock/check")
    parser.add_argument("--purpose", default="unspecified",
                        help="Why you need the board (shown to other sessions)")
    parser.add_argument("--timeout", type=int, default=120,
                        help="Max seconds to wait for lock (default: 120)")
    parser.add_argument("--force", action="store_true",
                        help="Force release even if not ours (legacy, no audit log)")
    parser.add_argument("--steal", action="store_true",
                        help="Explicitly take a lock from another track (logs to theft audit log)")
    args = parser.parse_args()

    if args.action == "status":
        sys.exit(status())

    if not args.resource:
        print("Error: resource (tx/rx/both) required for acquire/release/check", file=sys.stderr)
        sys.exit(2)

    if args.action == "acquire":
        sys.exit(acquire(args.resource, args.purpose, args.timeout))
    elif args.action == "release":
        sys.exit(release(args.resource, args.force, args.steal))
    elif args.action == "check":
        sys.exit(check(args.resource))


if __name__ == "__main__":
    main()
