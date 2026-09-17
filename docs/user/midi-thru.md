# MIDI Routing Matrix

MCM routes MIDI between three places: its **USB** port, its **5-pin DIN** port, and **the pedal itself**. Every path from a source to a destination is an independent on/off switch, so the pedal can sit in the middle of a MIDI chain — between your computer and a downstream device, or inside a ring of several Captains — without you having to choose one connection or the other.

In the Config Editor these live in the **MIDI Routing** pane as a 3×3 matrix: rows are the source, columns are the destination.

## The matrix

| From ＼ To | USB | 5-pin DIN | This pedal |
|---|---|---|---|
| **USB** | USB → USB (**off**) | USB → DIN (**on**) | USB → pedal (**on**) |
| **5-pin DIN** | DIN → USB (**on**) | DIN → DIN (**on**) | DIN → pedal (**on**) |
| **This pedal** | pedal → USB (**on**) | pedal → DIN (**on**) | — |

The bold value is the default. The pedal→pedal corner is not a route — a pedal "routing to itself" is just the button doing its job.

### Thru routes (port to port)

| Route | Config key | Typical use |
|---|---|---|
| **USB → DIN** | `midi_thru_usb_to_din` | Forward your DAW's MIDI out to another pedal or module on the 5-pin chain |
| **DIN → USB** | `midi_thru_din_to_usb` | Let a MIDI foot controller or keyboard upstream reach your DAW through the pedal |
| **DIN → DIN** | `midi_thru_din_to_din` | Classic MIDI THRU — daisy-chain other 5-pin devices downstream |
| **USB → USB** | `midi_thru_usb_to_usb` | Niche: echo the host's own output back to itself |

DIN→DIN's default matches the OEM firmware, so daisy-chaining behaves the way you'd expect coming from stock. USB→USB defaults **off** because it's a loopback: if your DAW also has its own MIDI echo/thru enabled, turning this on too can double up notes or create a feedback loop between the two echoes.

### Local routes (the pedal as a source and a destination)

| Route | Config key | What it controls |
|---|---|---|
| **pedal → USB** | `midi_local_to_usb` | Whether this pedal's own button, encoder and expression messages go out the USB port |
| **pedal → DIN** | `midi_local_to_din` | Same, out the 5-pin DIN port |
| **USB → pedal** | `midi_usb_to_local` | Whether messages arriving on USB are acted on — button matching, LED updates, select-group tracking, page control |
| **DIN → pedal** | `midi_din_to_local` | Same, for messages arriving on the 5-pin DIN input |

All four default **on**, which is exactly how the pedal behaved before these routes existed. Turning an input's →pedal route off makes that port **forward-only**: messages still pass through per the thru routes, the pedal just stops reacting to them.

Every route is a plain boolean in the config:

```jsonc
{
  "midi_thru_usb_to_din": true,
  "midi_thru_din_to_usb": true,
  "midi_thru_din_to_din": true,
  "midi_thru_usb_to_usb": false,

  "midi_local_to_usb": true,
  "midi_local_to_din": true,
  "midi_usb_to_local": true,
  "midi_din_to_local": true
}
```

## Processing order: local dispatch, then forwarding

For each incoming message the pedal does two independent things, in this order:

1. **Acts on it** — but only if that port's →pedal route is on. This is where [state sync, select sync](./inbound-midi.md), and [page control](./page-control.md) happen.
2. **Forwards it** — on whichever thru routes are enabled, carrying the original channel.

The two never gate each other. A message the pedal ignores (because its →pedal route is off) is still forwarded, and a message short-circuited by Page Control before it reaches button matching is still forwarded too. Likewise, turning thru routes off never stops the pedal from reacting to a message it receives.

## Worked example: pedal in the middle of a chain

A synth's 5-pin MIDI out feeds the pedal's DIN in, and the pedal's USB feeds your DAW. You also want the DAW to be able to drive a drum machine on the DIN out.

- `midi_thru_din_to_usb: true` — synth notes reach the DAW
- `midi_thru_usb_to_din: true` — DAW output reaches the drum machine
- `midi_thru_din_to_din: false` — no need to also forward the synth back out its own DIN chain

With this setup the pedal is fully transparent for both directions of that chain, while still reading every message for its own button/page state.

## Worked example: a MIDI ring of several Captains

Daisy-chaining Captains over DIN is one-way, so only the USB-connected device ever hears the host. Closing the chain into a **ring** — the last pedal's DIN out looping back into the first pedal's DIN in — fixes that: host messages travel all the way around and reach every device.

The catch is at the device that closes the ring — the one whose DIN out starts the chain and whose DIN in receives the tail of it, typically the USB-connected pedal. Without changes, its own messages lap the ring and arrive back at its own DIN input, where DIN→USB thru forwards them to the host a **second** time, and host messages it already handled over USB get processed **again** on the way past.

On that ring-closing device, turn off three routes:

```jsonc
{
  "midi_thru_din_to_din": false,   // messages don't circulate the ring forever
  "midi_local_to_din": false,      // its own messages never enter the ring
  "midi_din_to_local": false       // it doesn't re-process what it already handled over USB
}
```

Leave `midi_thru_din_to_usb` on — that's what carries the other pedals' messages to the host. The other pedals in the ring keep their defaults.

## Two warnings the editor will show you

- **"This pedal's switches send nothing"** — both `midi_local_to_usb` and `midi_local_to_din` are off, so button, encoder and expression messages go nowhere. Turn at least one back on.
- **"This pedal ignores all incoming MIDI"** — both `midi_usb_to_local` and `midi_din_to_local` are off, so nothing matches buttons, drives LEDs, or tracks select groups. Thru still passes messages along, but the pedal is deaf.

Both are warnings, not errors — they're legitimate settings for a forward-only or send-only node in a larger rig.

## Safety note on USB → USB

Leave `midi_thru_usb_to_usb` off unless you have a specific routing need for it. Because it echoes the host's own MIDI output straight back to the host, the most common symptom of accidentally enabling it is duplicate or stuck notes when your DAW's own MIDI echo/thru setting is also on — the two echoes compound.
