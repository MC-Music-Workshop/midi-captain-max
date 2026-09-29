# MIDI Learn

If your DAW, Gig Performer rig or modeler is already set up with MIDI, you don't have to copy the numbers across by hand. Click **Learn** on a button in the config editor, send the message from your host, and the button takes it on.

## How to learn a button

1. Connect the pedal and open it in the config editor, the same way you would to edit its config.
2. On the button you want to assign, click **Learn**. It changes to **Listening… ✕**.
3. From your host, send the message you want the button to send. For example, move the Gig Performer widget or trigger the DAW mapping so it transmits the CC, note or program change to the pedal.
4. The button's **Type**, **Channel** and **CC** / **Note** / **Program** fill in from that message, and the footer confirms what was learned, for example `Button 3: learned CC20 on Ch1 (USB)`.
5. Click **Save** to write the change to the pedal. Learn edits the form like any other field, so **Undo** works too.

To stop listening without learning anything, click **Listening… ✕**. Clicking **Learn** on another button moves listening to that button. If nothing arrives within 30 seconds, Learn gives up and the footer says so.

## What gets learned

| Incoming message | Button becomes | Fields set |
|------------------|----------------|------------|
| Control Change | **CC** | Channel, CC |
| Note On / Note Off | **Note** | Channel, Note |
| Program Change | **PC** | Channel, Program |

- Only the message's identity is learned. **ON/OFF Value** and **Vel ON/OFF** stay as they were, because a single incoming `0` or Note Off doesn't tell the pedal what your on and off values should be. Set them yourself if your host needs something other than the defaults.
- The channel is always set on the button itself, so the button keeps using it even if you change the global channel later.
- If the button's **Mode** doesn't exist for the new type, it switches to **Toggle**. For example, **Flash** is PC-only, and **Select** isn't available for Note buttons.
- Learn isn't offered for buttons in **Keytimes** mode. Their messages live in the short and long cycle entries.

## Where the message has to come from

Learn listens to what the pedal itself receives, over **USB** or **5-pin DIN** MIDI In. Point your host's MIDI output at the pedal, just as you would for [inbound MIDI](./inbound-midi.md) button sync.

If Learn times out even though your host is sending:

- **Check the routing:** the [routing matrix](./midi-thru.md) must pass that input to **This pedal**. A forward-only input never reaches the pedal, so there's nothing to learn.
- **Close serial monitors:** Learn reads the pedal's serial console. Quit `screen`, `tio` or any other program that has the console open.
- **Check the message type:** Learn only picks up CC, Note and Program Change messages. Clock, SysEx and pitch bend are ignored.
