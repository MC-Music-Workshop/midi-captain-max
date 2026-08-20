# MIDI THRU Routing Matrix

MCM can forward inbound MIDI back out again, independently on four distinct paths between its USB and 5-pin DIN ports. This lets the pedal sit in the middle of a MIDI chain — between your computer and a downstream device, for instance — without you having to choose one connection or the other.

## The four routes

| Route | Direction | Default | Typical use |
|---|---|---|---|
| **USB → DIN** | host → hardware downstream | **On** | Forward your DAW's MIDI out to another pedal or module on the 5-pin chain |
| **DIN → USB** | hardware upstream → host | **On** | Let a MIDI foot controller or keyboard upstream reach your DAW through the pedal |
| **DIN → DIN** | hardware → hardware | **On** | Classic MIDI THRU — daisy-chain other 5-pin devices downstream |
| **USB → USB** | host → host (loopback) | **Off** | Niche: echo the host's own output back to itself |

The two cross-thru routes (USB↔DIN) and DIN→DIN pass-through are all on by default. DIN→DIN's default in particular matches the OEM firmware, so daisy-chaining behaves the way you'd expect coming from stock. USB→USB defaults off because it's a loopback: if your DAW also has its own MIDI echo/thru enabled, turning this on too can double up notes or create a feedback loop between the two echoes.

Each route is an independent boolean — enable any combination:

```jsonc
{
  "midi_thru_usb_to_din": true,
  "midi_thru_din_to_usb": true,
  "midi_thru_din_to_din": true,
  "midi_thru_usb_to_usb": false
}
```

In the Config Editor, these four checkboxes appear as a 2×2 matrix under **MIDI Thru** — rows are the input, columns are the output, matching the table above.

## Processing order: buttons and pages always see the message first

THRU forwarding happens **after** MCM has already processed the message for its own button/page logic — every inbound MIDI message is evaluated for [state sync, select sync](./inbound-midi.md), and [page control](./page-control.md) *regardless* of your THRU settings. THRU is purely about whether that same message also gets relayed to the other port; it never gates or delays what the pedal does with the message itself.

This also means a message that gets short-circuited by Page Control (never reaching button matching) is still forwarded downstream on whatever THRU routes are enabled — Page Control and THRU are independent layers.

## Worked example: pedal in the middle of a chain

A synth's 5-pin MIDI out feeds the pedal's DIN in, and the pedal's USB feeds your DAW. You also want the DAW to be able to drive a drum machine on the DIN out.

- `midi_thru_din_to_usb: true` — synth notes reach the DAW
- `midi_thru_usb_to_din: true` — DAW output reaches the drum machine
- `midi_thru_din_to_din: false` — no need to also forward the synth back out its own DIN chain

With this setup the pedal is fully transparent for both directions of that chain, while still reading every message for its own button/page state.

## Safety note on USB → USB

Leave `midi_thru_usb_to_usb` off unless you have a specific routing need for it. Because it echoes the host's own MIDI output straight back to the host, the most common symptom of accidentally enabling it is duplicate or stuck notes when your DAW's own MIDI echo/thru setting is also on — the two echoes compound.
