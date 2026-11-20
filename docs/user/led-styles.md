# LED Styles: Multi-Color, Flash and Spin

Every footswitch has a ring of **three LEDs**. Normally all three show the button's **LED Color**, lit when the button is on and dimmed (or dark) when it's off. LED styles let you go further for each state:

- **Custom colors**: give each of the three LEDs its own color, e.g. red, white, green. Any of them can be `off`.
- **Flash**: the LEDs blink on and off.
- **Spin**: the colors rotate around the ring. With one color, a single lit LED chases around.

LED styles change the LEDs only. The switch's tile on the screen keeps following **LED Color**.

## Where to find them

On a regular button (Toggle, Momentary, Flash or Select), open the button and look below **LED Color / LED Off Mode / LED Off Color**. There are two boxes:

| Box | Controls |
|---|---|
| **LED when on** | how the LEDs look while the button is on, including the brief flash of a PC button |
| **LED when off** | how the LEDs look while the button is off |

In **Keytimes** mode, each tap or hold entry gets its own **LEDs** box instead, next to its Color, dim and label (see [Keytimes](./keytimes.md)).

Each box has:

| Field | What it does |
|---|---|
| preview | three dots that play exactly what the pedal will show |
| **Custom colors** | tick to pick each LED's color. Unticked, the state's usual color fills all three LEDs |
| **Animation** | **Solid**, **Flash** or **Spin** |
| **Speed (ms)** | Flash: how long the LEDs stay on, and then off. Spin: how long each position lasts. 50–5000, default 250 |

You can add an animation without custom colors: a red button with **LED when on** set to **Flash** simply blinks red.

## How the off state is worked out

When **LED when off** has custom colors, those are shown at full brightness and **LED Off Color** and **LED Off Mode** are ignored. Otherwise the pedal uses, in order:

1. **LED Off Color**, if set.
2. **LED Off Mode: off**: the LEDs go dark.
3. **LED Off Mode: dim**: a dimmed copy of the on look. If **LED when on** has custom colors, you get those colors dimmed, not a dimmed **LED Color**.

An animation on **LED when on** never carries over to the off state. Give **LED when off** its own animation if you want the off state to move too.

## Keytimes entries

An entry's **LEDs** box follows the same tap/hold rules as its **Color**. The most recent press owns the LEDs, and **Long-press color overrides short-press color** keeps a hold's look on top. An entry with custom colors counts as having a color, even if its Color is left on `(inherit)`. Ticking **dim** dims the custom colors too. A tap entry with Color `off` still turns the LEDs off, whatever its LEDs box says.

Because a host can pick a keytimes entry with **Listen CC** and **Receive value** (see [Inbound MIDI](./inbound-midi.md)), the host can choose the animation as well as the color.

## Not available on

- **CC+ / CC- buttons in Slots mode**: each slot's color owns the LEDs. (Step mode buttons do get LED styles.)
- **The encoder push**, which has no LEDs.

## Scenarios

**Looper track.** A Keytimes button with **Listen CC** set to the looper's state output. Entry 1 (Receive value 1, label `REC`): Custom colors red/red/red, **Flash** at 250 ms. Entry 2 (value 2, `PLAY`): Color green, **Spin** at 150 ms. Entry 3 (value 0, `STOP`): Color white, dim. The pedal now shows recording, playing and stopped at a glance on a dark stage.

**Two-tone patch indicator.** **LED when on**: Custom colors blue / white / blue, **Spin** at 200. **LED when off**: Custom colors off / white / off. Off shows a single white LED; on spins.

**"Armed" reminder.** Leave **LED when on** alone and set **LED when off** to Custom colors orange / off / orange with **Flash** at 600, so a disarmed effect keeps nudging you.

The example config `config-example-led-styles.json` in the firmware folder sets up all of these on one STD10 page.
