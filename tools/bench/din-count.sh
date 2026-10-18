#!/usr/bin/env bash
# DIN receive count: does the pedal receive every message sent to its DIN MIDI IN?
#
# Sends N alternating note 60 on/off (Ch 4) through a USB-to-DIN cable into the
# pedal's MIDI IN, and counts what the pedal forwards back to the computer over
# USB via its default-on DIN->USB thru. Every note toggles button 1, so every
# message forces a repaint.
#
#   paced: one message every 60 ms (control: the pedal must keep up)
#   burst: all N messages in a single sendmidi call (back to back at 31250 baud)
#
# Pass: paced N/N and burst N/N. Exits nonzero on FAIL.
#
# Config: tools/bench/configs/nano4-207-serial-din-test.json (notes 60-63 on
#   Ch 4). Any config with a note 60 button on Ch 4 works.
# Setup: pedal on USB; USB-to-DIN cable OUT -> pedal MIDI IN. Only one pedal may
#   be connected: every MIDI Captain enumerates under the same port name.
# Needs: sendmidi + receivemidi (brew install gbevin/tools/sendmidi gbevin/tools/receivemidi)
#
# Usage: tools/bench/din-count.sh [--pedal-port NAME] [--din-port NAME] [N]
#   sendmidi list   # shows port names

set -euo pipefail

pedal_port="Pico Midi Captain- usb_midi.ports[0]"
din_port="USB MIDI Interface"
n=100

while [ $# -gt 0 ]; do
  case "$1" in
    --pedal-port) pedal_port="$2"; shift 2 ;;
    --din-port) din_port="$2"; shift 2 ;;
    -h|--help) sed -n '2,21p' "$0"; exit 0 ;;
    *) n="$1"; shift ;;
  esac
done

fail() {
  echo "FAIL $*"
  exit 1
}

for tool in sendmidi receivemidi; do
  command -v "$tool" >/dev/null || fail "$tool not installed (brew install gbevin/tools/$tool)"
done

ports="$(sendmidi list)"
for port in "$pedal_port" "$din_port"; do
  # -x: whole-line match, -F: literal (port names contain [ ] and .)
  grep -qxF "$port" <<<"$ports" || fail "MIDI port '$port' not found (sendmidi list)"
done

log="$(mktemp -t din-count)"
rx_pid=""
cleanup() {
  if [ -n "$rx_pid" ]; then kill "$rx_pid" 2>/dev/null || true; fi
  rm -f "$log"
}
trap cleanup EXIT

# Runs one mode and sets $count to how many notes the pedal forwarded back.
# Not called via $(...): a subshell would hide rx_pid from the EXIT trap.
count=0
count_mode() {
  local mode=$1 i args
  : >"$log"
  receivemidi dev "$pedal_port" >"$log" 2>&1 &
  rx_pid=$!
  sleep 1
  if [ "$mode" = burst ]; then
    args=(ch 4)
    for ((i = 0; i < n; i++)); do args+=(on 60 $((i % 2 ? 0 : 127))); done
    sendmidi dev "$din_port" "${args[@]}" || fail "sendmidi to '$din_port' failed"
  else
    for ((i = 0; i < n; i++)); do
      sendmidi dev "$din_port" ch 4 on 60 $((i % 2 ? 0 : 127)) || fail "sendmidi to '$din_port' failed"
      sleep 0.06
    done
  fi
  # Let the pedal drain its backlog before counting.
  sleep 3
  kill "$rx_pid" 2>/dev/null || true
  wait "$rx_pid" 2>/dev/null || true
  rx_pid=""
  # grep -c exits 1 on zero matches; still prints 0.
  count="$(grep -c 'note-' "$log" || true)"
}

count_mode paced
paced=$count
count_mode burst
burst=$count

summary="paced $paced/$n, burst $burst/$n"
if [ "$paced" -eq "$n" ] && [ "$burst" -eq "$n" ]; then
  echo "PASS $summary"
else
  echo "FAIL $summary"
  exit 1
fi
