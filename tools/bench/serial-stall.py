#!/usr/bin/env python3
"""Serial console stall: does an unread serial console slow down or wedge the pedal?

Flips the pedal's page over USB MIDI (page_control jump CC100, values 0/1 on
Ch 4) once per gap, so the pedal prints one `[PAGE]` line per flip to its serial
console. Any MIDI send that takes longer than 0.2 s or fails counts as a stall.

  read: open the serial console and keep reading it (baseline: every line
        should arrive).
  hold: open it read-only and never read, like a suspended `screen`, so the
        host's buffer fills up. At the end, drain and report what had queued.

Pass: no slow or failed sends; in read mode also `[PAGE]` lines == flips
(within --tolerance). In hold mode the line count is informational: macOS
buffers about 45 KB of unread output, then drops the rest.

Config: tools/bench/configs/nano4-207-serial-din-test.json (2 pages,
  page_control jump CC100 on Ch 4). The gap must stay at or above 0.25 s:
  faster, and the pedal merges page changes into one `[PAGE]` line.
Setup: pedal on USB only, nothing else holding its serial port open (close
  `screen`, the Config Editor's console). Only one pedal may be connected.
Needs: sendmidi (brew install gbevin/tools/sendmidi). Stdlib only.

Usage: python3 tools/bench/serial-stall.py read|hold [--flips N] [--gap S]
         [--pedal-port NAME] [--serial /dev/cu.usbmodemXXXX]
"""

import argparse
import glob
import os
import subprocess
import sys
import time

PEDAL_PORT = "Pico Midi Captain- usb_midi.ports[0]"
SLOW_SEND_S = 0.2
DEFAULT_FLIPS = {"read": 200, "hold": 2000}


def count_page_lines(buf):
  return buf.count(b"[PAGE]")


def evaluate(mode, flips, lines, slow, tolerance=2):
  """Return (passed, summary) for one run."""
  passed = slow == 0
  if mode == "read":
    passed = passed and abs(lines - flips) <= tolerance
  return passed, f"{mode}: {flips} flips, slow/failed sends {slow}, [PAGE] lines {lines}"


def fail(msg):
  print(f"FAIL {msg}")
  sys.exit(1)


def main():
  ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
  ap.add_argument("mode", choices=["read", "hold"])
  ap.add_argument("--flips", type=int, help="page flips (default: 200 read, 2000 hold)")
  ap.add_argument("--gap", type=float, default=0.25, help="seconds per flip (default 0.25)")
  ap.add_argument("--tolerance", type=int, default=2, help="read mode: allowed |lines - flips|")
  ap.add_argument("--pedal-port", default=PEDAL_PORT)
  ap.add_argument("--serial", help="serial device (default: first /dev/cu.usbmodem*)")
  args = ap.parse_args()
  flips = args.flips or DEFAULT_FLIPS[args.mode]

  try:
    ports = subprocess.run(["sendmidi", "list"], capture_output=True, text=True, timeout=10).stdout
  except FileNotFoundError:
    fail("sendmidi not installed (brew install gbevin/tools/sendmidi)")
  if args.pedal_port not in ports.splitlines():
    fail(f"MIDI port '{args.pedal_port}' not found (sendmidi list)")

  dev = args.serial or next(iter(sorted(glob.glob("/dev/cu.usbmodem*"))), None)
  if not dev or not os.path.exists(dev):
    fail("no serial device found (/dev/cu.usbmodem*); pass --serial")

  fd = os.open(dev, os.O_RDONLY | os.O_NONBLOCK)
  buf = bytearray()

  def drain():
    while True:
      try:
        chunk = os.read(fd, 4096)
      except BlockingIOError:
        return
      if not chunk:
        return
      buf.extend(chunk)

  print(f"{args.mode}: {flips} flips every {args.gap}s via '{args.pedal_port}', console {dev}", flush=True)
  t0 = time.monotonic()
  slow = 0
  try:
    for i in range(flips):
      t = time.monotonic()
      cmd = ["sendmidi", "dev", args.pedal_port, "ch", "4", "cc", "100", str((i + 1) % 2)]
      try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        rc, err = r.returncode, r.stderr.strip()[:60]
      except subprocess.TimeoutExpired:
        rc, err = "timeout", ""
      dt = time.monotonic() - t
      if dt > SLOW_SEND_S or rc:
        slow += 1
        print(f"flip {i + 1}: send took {dt:.2f}s rc={rc} {err}", flush=True)
      if args.mode == "read":
        drain()
      time.sleep(max(0, args.gap - dt))
      if (i + 1) % 50 == 0:
        print(f"{i + 1} flips at {time.monotonic() - t0:.1f}s, [PAGE] lines read so far {count_page_lines(buf)}", flush=True)
    time.sleep(1)
    drain()
  finally:
    os.close(fd)

  passed, summary = evaluate(args.mode, flips, count_page_lines(buf), slow, args.tolerance)
  noun = "buffered" if args.mode == "hold" else "read"
  print(f"{'PASS' if passed else 'FAIL'} {summary}, bytes {noun} {len(buf)}")
  sys.exit(0 if passed else 1)


if __name__ == "__main__":
  main()
