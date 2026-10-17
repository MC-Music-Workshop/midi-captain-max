#!/usr/bin/env bash
# Simulate Visibox omni-mode LED feedback (#205) to bench-test MIDI RX under load.
#
# Every ~300 ms: notes 60-69 on all 16 channels (160 messages), with the
# "playing" clip's note on and the rest off. Every CLIP_SECS seconds the
# playing clip advances and the state is sent 3x back to back (480 messages),
# like a Visibox clip start.
#
# Needs sendmidi (brew install gbevin/tools/sendmidi).
#
# Usage: tools/visibox-flood.sh "<MIDI output port>" [seconds] [clip_secs]
#   sendmidi list   # shows port names

set -euo pipefail

dev="${1:?usage: $0 \"<MIDI output port>\" [seconds] [clip_secs]}"
secs="${2:-30}"
clip_secs="${3:-4}"

# One full LED-state refresh as sendmidi arguments.
refresh_args() {
  local playing=$1 args=() ch note
  for ch in $(seq 1 16); do
    args+=(ch "$ch")
    for note in $(seq 60 69); do
      if (( note == playing )); then
        args+=(on "$note" 127)
      else
        args+=(off "$note" 0)
      fi
    done
  done
  echo "${args[@]}"
}

# When the pedal reads too slowly, CoreMIDI rejects the send and sendmidi
# reports the port as missing. Count it and keep going instead of exiting.
failed=0
send() {
  sendmidi dev "$dev" "$@" 2>/dev/null || {
    failed=$((failed + 1))
    echo "Send rejected by CoreMIDI: pedal isn't keeping up" >&2
  }
}

playing=60
# SECONDS is a bash builtin counting seconds since the shell started.
end=$((SECONDS + secs))
next_clip=$((SECONDS + clip_secs))

echo "Flooding '$dev' for ${secs}s; playing clip note $playing"
while (( SECONDS < end )); do
  if (( SECONDS >= next_clip )); then
    playing=$(( playing == 69 ? 60 : playing + 1 ))
    next_clip=$((SECONDS + clip_secs))
    echo "Clip start: playing note $playing"
    # word splitting of $(...) is intentional: each token is one sendmidi argument
    # shellcheck disable=SC2046
    for _ in 1 2 3; do send $(refresh_args "$playing"); done
  else
    # shellcheck disable=SC2046
    send $(refresh_args "$playing")
  fi
  sleep 0.3
done
echo "Stopped. LEDs should settle on note $playing within a moment and then stay still."
echo "Rejected sends: $failed (0 means the pedal kept up)"
