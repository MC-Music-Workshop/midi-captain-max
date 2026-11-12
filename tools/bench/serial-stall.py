#!/usr/bin/env python3
"""Serial console stall: does an unread serial console slow down or wedge the pedal?

Flips the pedal's page over USB MIDI (page_control jump CC100, values 0/1 on
Ch 4) once per gap, so the pedal prints one `[PAGE]` line per flip to its serial
console. Every flip goes through one long-running `sendmidi --` process: on
macOS 27, starting a new MIDI client per message fails every ~10 s with a ~5 s
stall, from the OS, not the pedal. A send that blocks over 0.2 s, an error from
sendmidi, or sendmidi exiting counts as a failed send.

  read: open the serial console and keep reading it (baseline: every line
        should arrive).
  hold: open it read-only and never read, like a suspended `screen`, so the
        host's buffer fills up. At the end, drain and report what had queued,
        then probe: 10 more flips 1 s apart while reading, which must all
        print, so a wedged pedal fails.

Pass: no failed sends; in read mode also `[PAGE]` lines == flips (within
--tolerance); in hold mode the probe's `[PAGE]` lines == 10 (within
--tolerance). The hold run's own line count is informational: macOS 26
buffered ~45 KB of unread output and dropped the rest; macOS 27.2 kept all of
a 2000-flip run (77 KB).

Config: tools/bench/configs/nano4-207-serial-din-test.json (2 pages,
  page_control jump CC100 on Ch 4), or std10-207-serial-din-test.json. If
  page changes arrive faster than the pedal redraws a page, it merges them
  (no `[PAGE]` line, same final page): keep the gap at or above 0.25 s on a
  NANO4 and 0.4 s on an STD10 (it merges below ~0.35 s).
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
PROBE_FLIPS = 10
PROBE_GAP_S = 1.0


def count_page_lines(buf):
  return buf.count(b"[PAGE]")


def evaluate(mode, flips, lines, slow, tolerance=2, probe=None):
  """Return (passed, summary) for one run. probe: hold mode's post-hold [PAGE] lines."""
  passed = slow == 0
  summary = f"{mode}: {flips} flips, slow/failed sends {slow}, [PAGE] lines {lines}"
  if mode == "read":
    passed = passed and abs(lines - flips) <= tolerance
  else:
    passed = passed and probe is not None and abs(probe - PROBE_FLIPS) <= tolerance
    summary += f", probe {probe}/{PROBE_FLIPS}"
  return passed, summary


def fail(msg):
  print(f"FAIL {msg}")
  sys.exit(1)


def send(sender, value):
  """Send one flip through the long-running sendmidi; return an error or None."""
  try:
    sender.stdin.write(f"ch 4 cc 100 {value}\n".encode())
    sender.stdin.flush()
  except BrokenPipeError:
    pass
  if sender.poll() is not None:
    return f"sendmidi exited rc={sender.returncode}"
  try:
    err = os.read(sender.stderr.fileno(), 4096)
  except BlockingIOError:
    return None
  return err.decode(errors="replace").strip()[:60] or None


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

  # Retried: `sendmidi list` is a short-lived MIDI client too, so macOS 27 can
  # fail it (see above) and briefly report no ports.
  for attempt in range(3):
    try:
      ports = subprocess.run(["sendmidi", "list"], capture_output=True, text=True, timeout=10).stdout
    except FileNotFoundError:
      fail("sendmidi not installed (brew install gbevin/tools/sendmidi)")
    if args.pedal_port in ports.splitlines():
      break
    time.sleep(3)
  else:
    fail(f"MIDI port '{args.pedal_port}' not found (sendmidi list)")

  dev = args.serial or next(iter(sorted(glob.glob("/dev/cu.usbmodem*"))), None)
  if not dev or not os.path.exists(dev):
    fail("no serial device found (/dev/cu.usbmodem*); pass --serial")

  fd = os.open(dev, os.O_RDONLY | os.O_NONBLOCK)
  buf = bytearray()
  # `--` makes sendmidi read commands from stdin until it closes: one MIDI
  # client for the whole run.
  sender = subprocess.Popen(["sendmidi", "dev", args.pedal_port, "--"],
                            stdin=subprocess.PIPE, stderr=subprocess.PIPE)
  os.set_blocking(sender.stderr.fileno(), False)

  def drain():
    while True:
      try:
        chunk = os.read(fd, 4096)
      except BlockingIOError:
        return
      if not chunk:
        return
      buf.extend(chunk)

  def drain_until_quiet(quiet_s=1.0, cap_s=30.0):
    # After a hold the backlog arrives in chunks over a fraction of a second;
    # one drain() would stop at the first gap.
    end, last = time.monotonic() + cap_s, (len(buf), time.monotonic())
    while time.monotonic() < end and time.monotonic() - last[1] < quiet_s:
      drain()
      if len(buf) != last[0]:
        last = (len(buf), time.monotonic())
      time.sleep(0.05)

  print(f"{args.mode}: {flips} flips every {args.gap}s via '{args.pedal_port}', console {dev}", flush=True)
  t0 = time.monotonic()
  slow = 0
  probe = None
  try:
    for i in range(flips):
      t = time.monotonic()
      err = send(sender, (i + 1) % 2)
      dt = time.monotonic() - t
      if dt > SLOW_SEND_S or err:
        slow += 1
        print(f"flip {i + 1}: send took {dt:.2f}s {err or ''}", flush=True)
      if args.mode == "read":
        drain()
      time.sleep(max(0, args.gap - dt))
      if (i + 1) % 50 == 0:
        print(f"{i + 1} flips at {time.monotonic() - t0:.1f}s, [PAGE] lines read so far {count_page_lines(buf)}", flush=True)
    time.sleep(1)
    drain_until_quiet()
    lines, held = count_page_lines(buf), len(buf)
    if args.mode == "hold":
      for i in range(flips, flips + PROBE_FLIPS):
        err = send(sender, (i + 1) % 2)
        if err:
          slow += 1
          print(f"probe flip {i + 1 - flips}: {err}", flush=True)
        time.sleep(PROBE_GAP_S)
        drain()
      drain_until_quiet()
      probe = count_page_lines(buf) - lines
  finally:
    os.close(fd)
    sender.stdin.close()
    sender.wait(timeout=5)

  passed, summary = evaluate(args.mode, flips, lines, slow, args.tolerance, probe)
  noun = "buffered" if args.mode == "hold" else "read"
  print(f"{'PASS' if passed else 'FAIL'} {summary}, bytes {noun} {held}")
  sys.exit(0 if passed else 1)


if __name__ == "__main__":
  main()
