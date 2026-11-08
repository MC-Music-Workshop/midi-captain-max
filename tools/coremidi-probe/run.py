#!/usr/bin/env python3
"""CoreMIDI client probe: does starting short-lived MIDI clients fail on this macOS?

Found on macOS 27.2: when no other MIDI client is open, a new short-lived
client fails every ~7-10 s (CoreMIDI -304, "Couldn't find MIDI output", then a
~5 s stall), so one `sendmidi` per message breaks. While any long-running
client is open (a `receivemidi`, a DAW), the same sends all succeed.

Phase A, no other MIDI client open (one process per call):
  sendmidi list            a short-lived sendmidi client
  probe client only        probe.swift (CoreMIDI only, no sendmidi): create a
                           client and an output port, exit
Phase B, one long-running `receivemidi virt` holding a virtual port open:
  sendmidi per message     a new sendmidi per message to that port
  probe per message        a new probe per message to that port
  sendmidi --              one sendmidi reading commands from stdin

For each mode: failed calls, calls slower than 1 s, slowest call, and in phase
B how many messages arrived. Exit status is 0 either way: this measures, it
doesn't gate. `.github/workflows/coremidi-probe.yml` runs it on each hosted
macOS version.

Needs: sendmidi + receivemidi (brew install gbevin/tools/sendmidi
  gbevin/tools/receivemidi), and probe.swift compiled:
  xcrun swiftc -O -o probe tools/coremidi-probe/probe.swift
Close anything else using MIDI first (DAWs, the Config Editor's MIDI
  monitor), or phase A will look healthy on any macOS.

Usage: python3 tools/coremidi-probe/run.py --probe ./probe [--count N]
         [--gap S] [--json out.json]
"""

import argparse
import json
import os
import platform
import subprocess
import sys
import threading
import time

PORT = "coremidi-probe-in"
SLOW_S = 1.0


class Receiver:
  """One long-running `receivemidi virt` that counts control changes."""

  def __init__(self):
    self.count = 0
    self.proc = subprocess.Popen(["receivemidi", "virt", PORT], stdout=subprocess.PIPE, text=True, bufsize=1)
    threading.Thread(target=self._read, daemon=True).start()

  def _read(self):
    for line in self.proc.stdout:
      if "control-change" in line:
        self.count += 1

  def settled(self):
    """Count once nothing new has arrived for 1 s."""
    last = -1
    while last != self.count:
      last = self.count
      time.sleep(1)
    return self.count


def wait_for_port():
  # `sendmidi list` is a short-lived client too, so retry rather than trust one call.
  for _ in range(40):
    r = subprocess.run(["sendmidi", "list"], capture_output=True, text=True, timeout=30)
    if PORT in r.stdout.splitlines():
      return
    time.sleep(0.5)
  sys.exit(f"virtual port '{PORT}' never appeared in `sendmidi list`")


def per_call(argv_for, count, gap):
  """Run one process per call; return (failures, durations)."""
  failures, durations = [], []
  t0 = time.monotonic()
  for i in range(count):
    t = time.monotonic()
    try:
      r = subprocess.run(argv_for(i), capture_output=True, text=True, timeout=30)
      # sendmidi reports CoreMIDI errors on stderr, sometimes with exit status 0.
      err = (r.stderr.strip() or r.stdout.strip() or f"exit {r.returncode}") if r.returncode or r.stderr.strip() else ""
    except subprocess.TimeoutExpired:
      err = "timed out after 30 s"
    dt = time.monotonic() - t
    durations.append(dt)
    if err:
      failures.append({"call": i + 1, "at_s": round(t - t0, 1), "error": err.splitlines()[0][:80]})
    time.sleep(max(0, gap - dt))
  return failures, durations


def sendmidi_stdin(count, gap):
  """One `sendmidi --` fed one command line per message."""
  proc = subprocess.Popen(["sendmidi", "dev", PORT, "--"], stdin=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
  for i in range(count):
    proc.stdin.write(f"ch 1 cc 100 {(i + 1) % 2}\n")
    proc.stdin.flush()
    time.sleep(gap)
  proc.stdin.close()
  err = proc.stderr.read().strip()
  proc.wait(timeout=10)
  failures = [{"call": None, "at_s": None, "error": line[:80]} for line in err.splitlines()]
  if proc.returncode:
    failures.append({"call": None, "at_s": None, "error": f"sendmidi exited {proc.returncode}"})
  return failures, []


def other_midi_clients():
  """Best effort: processes that commonly hold MIDI clients open."""
  r = subprocess.run(["pgrep", "-lf", "receivemidi|sendmidi|Ableton|Logic Pro|GarageBand|MIDI Captain"],
                     capture_output=True, text=True)
  return [line for line in r.stdout.splitlines() if "pgrep" not in line]


def main():
  ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
  ap.add_argument("--probe", required=True, help="compiled probe.swift binary")
  ap.add_argument("--count", type=int, default=120, help="calls per mode (default 120)")
  ap.add_argument("--gap", type=float, default=0.25, help="seconds between calls (default 0.25)")
  ap.add_argument("--json", help="also write results here")
  args = ap.parse_args()
  probe = os.path.abspath(args.probe)

  env = {
    "macos": subprocess.run(["sw_vers", "-productVersion"], capture_output=True, text=True).stdout.strip(),
    "build": subprocess.run(["sw_vers", "-buildVersion"], capture_output=True, text=True).stdout.strip(),
    "arch": platform.machine(),
    "sendmidi": subprocess.run(["sendmidi", "--version"], capture_output=True, text=True).stdout.splitlines()[0],
    "other_midi_clients": other_midi_clients(),
  }
  if env["other_midi_clients"]:
    print(f"warning: other MIDI clients may be open, phase A can look healthy: {env['other_midi_clients']}")

  phase_a = [
    ("A", "sendmidi list", lambda: per_call(lambda i: ["sendmidi", "list"], args.count, args.gap)),
    ("A", "probe client only", lambda: per_call(lambda i: [probe, "-", "1", "0"], args.count, args.gap)),
  ]
  phase_b = [
    ("B", "sendmidi per message", lambda: per_call(
      lambda i: ["sendmidi", "dev", PORT, "ch", "1", "cc", "100", str((i + 1) % 2)], args.count, args.gap)),
    ("B", "probe per message", lambda: per_call(lambda i: [probe, PORT, "1", "0"], args.count, args.gap)),
    ("B", "sendmidi --", lambda: sendmidi_stdin(args.count, args.gap)),
  ]

  results = []

  def record(phase, name, run, rx=None):
    before = rx.settled() if rx else 0
    print(f"### {phase}: {name}", flush=True)
    failures, durations = run()
    received = rx.settled() - before if rx else None
    r = {
      "phase": phase, "mode": name, "calls": args.count, "failed": len(failures),
      "slow": sum(1 for d in durations if d > SLOW_S),
      "max_s": round(max(durations), 2) if durations else None,
      "received": received, "failures": failures,
    }
    results.append(r)
    print(f"failed {r['failed']}, slow {r['slow']}, max {r['max_s']} s, received {received}", flush=True)
    for f in failures[:5]:
      print(f"  {f}", flush=True)

  for phase, name, run in phase_a:
    record(phase, name, run)
  rx = Receiver()
  wait_for_port()
  time.sleep(1)
  for phase, name, run in phase_b:
    record(phase, name, run, rx)
  rx.proc.terminate()

  lines = [
    f"### macOS {env['macos']} ({env['build']}, {env['arch']}), {env['sendmidi']}",
    "",
    f"{args.count} calls per mode, {args.gap} s apart. Phase A: no other MIDI client open. "
    "Phase B: a `receivemidi` holds a virtual port open.",
    "",
    "| Phase | Mode | Failed | Calls > 1 s | Slowest call | Received |",
    "|-------|------|--------|-------------|--------------|----------|",
  ]
  for r in results:
    slowest = f"{r['max_s']} s" if r["max_s"] is not None else "n/a"
    received = f"{r['received']}/{r['calls']}" if r["received"] is not None else "n/a"
    lines.append(f"| {r['phase']} | {r['mode']} | {r['failed']} | {r['slow']} | {slowest} | {received} |")
  errors = sorted({f["error"] for r in results for f in r["failures"]})
  if errors:
    lines += ["", "Errors seen:", ""] + [f"- `{e}`" for e in errors]
  if env["other_midi_clients"]:
    lines += ["", f"Other MIDI clients possibly open: `{env['other_midi_clients']}`"]
  summary = "\n".join(lines) + "\n"
  print("\n" + summary)
  if os.environ.get("GITHUB_STEP_SUMMARY"):
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
      f.write(summary)
  if args.json:
    with open(args.json, "w") as f:
      json.dump({"env": env, "count": args.count, "gap": args.gap, "results": results}, f, indent=2)


if __name__ == "__main__":
  main()
