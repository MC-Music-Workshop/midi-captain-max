# Multiple Messages

Any button can send more than its own message. Under each button in the editor, **Also send** lists extra messages that go out right after the button's own one, in the order listed. Click **+ message** to add one.

The extras take the same message types as a [keytimes](./keytimes.md) entry: **CC**, **Note**, **PC Fixed**, **PC+** / **PC-**, **CC+** / **CC-**, [**HID**](./hid.md), and **Page+** / **Page-** / **Page Jump**. Each MIDI message has its own channel.

**CC+** / **CC-** here step a CC of their own: set its **CC**, and optionally **Step** (default 1), **Min** / **Max** (default 0–127, starting at Min) and **wrap** (on by default). The value is shared with any CC+ / CC- button on the same CC and channel, so they stay in step.

## When they're sent

Buttons that turn on and off get two lists: one for turning on, one for turning off.

| Mode | First list | Second list |
|------|------------|-------------|
| **Toggle** | when turned on | when turned off |
| **Momentary** | on press | on release |
| **Select** (CC, re-press set to **Deselect**) | when selected | when deselected |
| **Flash**, **Select**, page and CC+/CC- buttons | on press | — |

HID buttons in momentary mode only flash, so they get just the press list.

## Example

A toggle on CC 20 that switches an amp channel and the matching delay preset together:

- **Also send when turned on:** PC Fixed with program 12, then CC 30 with value 127 on channel 2
- **Also send when turned off:** PC Fixed with program 4, then CC 30 with value 0 on channel 2

Turning it on sends CC20=127, then PC12, then CC30=127 on channel 2. Turning it off sends CC20=0, PC4, CC30=0.

## Things to know

- Incoming MIDI only follows the button's own message. The extras don't change how the LED reacts to the host.
- A CC+ / CC- extra only picks up a value the host sends if a CC+ / CC- button on the same CC and channel is on the current page.
- In **keytimes** mode, these lists don't apply. Put the messages in the cycle entries instead.
