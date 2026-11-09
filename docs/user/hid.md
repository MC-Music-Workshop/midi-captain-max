# HID: Keyboard and Mouse

Any button can type a key or click the mouse instead of sending MIDI. Your computer sees the pedal as a USB keyboard and mouse, so HID works in any app with a keyboard shortcut: turning sheet-music pages, starting and stopping a DAW, advancing slides, muting a call.

HID only works over USB. It doesn't go out the 5-pin DIN port.

## Setting one up

In the Config Editor, set the button's **Type** to **HID**. Three fields appear:

| Field | What it does |
|---|---|
| **Action** | what happens to the key: **Send**, **Press**, **Release** or **Delay** (see below). Default is **Send** |
| **Key** | the key or mouse button, by name, e.g. `A`, `F5`, `Space`, `Mouse_L`. See [Key names](#key-names) |
| **Modifier** | an optional key held down with it: **Ctrl**, **Shift**, **Alt**, **Option (⌥)** or **Windows (⊞)** |

HID messages have no MIDI channel, so the channel field is hidden for them.

## Actions

| Action | What it does | Use it for |
|---|---|---|
| **Send** | presses and releases the key right away, like a quick tap | almost everything: shortcuts, page turns, transport |
| **Press** | presses the key and keeps it down | holding a key, or dragging with the mouse |
| **Release** | lets go of a key you pressed with **Press**. Key `all` lets go of every key and mouse button | ending a **Press** |
| **Delay** | waits, from 1 to 5000 ms (default 50). The **Key** and **Modifier** fields are replaced by **Delay (ms)** | spacing out messages in a list, for apps that miss keys sent too fast |

Every **Press** needs a matching **Release**, or the computer acts as if the key is stuck down. If that happens, a button with **Release** and key `all` clears it.

**Delay** pauses the whole pedal for its duration, so keep it short. Other switches don't respond until it's over.

## Modifiers

The **Modifier** is held down for the key's **Send** or **Press**. Each HID message takes one modifier.

| Modifier | Windows / Linux | macOS |
|---|---|---|
| **Ctrl** | Ctrl | Control (⌃) |
| **Shift** | Shift | Shift (⇧) |
| **Alt** | Alt | Option (⌥) |
| **Option (⌥)** | Alt | Option (⌥) |
| **Windows (⊞)** | Windows key | **Command (⌘)** |

On a Mac, most shortcuts use **Command**, so pick **Windows (⊞)**. For example, ⌘S is key `S` with modifier **Windows (⊞)**.

## Key names

Type the name into the **Key** field. Upper or lower case both work.

| Group | Names |
|---|---|
| Letters | `A` to `Z` |
| Digits | `0` to `9` (the top row, not the number pad) |
| Function keys | `F1` to `F12` |
| Arrows | `Up`, `Down`, `Left`, `Right` |
| Navigation | `Home`, `End`, `PageUp`, `PageDown` |
| Editing | `Enter`, `Space`, `Table` (the Tab key), `BackSpace`, `Del`, `Ins`, `Esc`, `Caps` (Caps Lock) |
| Other | `PrintS` (Print Screen), `Pause` |
| Mouse | `Mouse_L` (left click), `Mouse_R` (right click) |
| Release only | `all`: every held key and mouse button |

The editor doesn't check key names. A misspelled name, or a key not on this list (punctuation, the number pad, media keys), saves fine and does nothing when pressed.

## How the button behaves

A button with **Type** set to **HID** sends its action **when you press it**. Lifting your foot sends nothing. **Mode** only changes what the LED does:

| Mode | Each press | LED |
|---|---|---|
| **Toggle** (default) | sends the action | turns on and off on alternate presses |
| **Momentary** | sends the action | flashes briefly |
| **Keytimes (short/long)** | the entries decide | the entries decide |

**Momentary** doesn't hold the key while your foot is down. To do that, use **Keytimes**, below.

A **Delay** on its own doesn't light the LED, since nothing visible happened.

## HID in message lists

HID also works anywhere you can add messages:

- **Also send** on any button, after the button's own message. See [Multiple Messages](./multiple-messages.md).
- **Keytimes** entries, on press or release, for taps or holds. See [Keytimes](./keytimes.md).

In a list, pick **HID** as the message type. The **Action**, **Key**, **Modifier** and **Delay ms** fields work as above. Messages go out in the order listed, which is what makes **Press**, **Delay** and **Release** useful.

## Examples

**Turn sheet-music pages.** Two buttons, both **Type** HID, **Mode** Momentary: one with key `Right`, one with key `Left`. Many score readers and PDF viewers also take `PageDown` / `PageUp`.

**Save in a DAW.** **Type** HID, key `S`. Modifier **Ctrl** on Windows, **Windows (⊞)** for ⌘S on a Mac.

**Hold a key while your foot is down** (push-to-talk, a held mouse click). Set **Mode** to **Keytimes (short/long)**, then:

1. Add one **Short Press Cycle** entry. In **short_down**, add HID **Press** with your key. In **short_up**, add HID **Release** with the same key.
2. Add one **Long Press Cycle** entry. In **long_up**, add the same HID **Release**.

A quick tap releases through **short_up**. Holding past the long-press threshold skips **short_up**, so the long entry's **long_up** releases instead. Without it, a long hold leaves the key stuck down.

**Two keys in a row.** **Type** HID, **Mode** Momentary, key `Esc`. Under **Also send**, add HID **Delay** of 100 ms, then HID **Send** with key `Space`. One press sends Esc, waits, then sends Space.

## Things to know

- **At least one button needs Type HID.** The pedal shows up as a keyboard and mouse only when at least one button, on any page or the encoder push, has its **Type** set to **HID**. HID messages that only appear in **Also send** lists or **Keytimes** entries don't count. If those do nothing, set any spare button's **Type** to **HID**.
- **The pedal is a keyboard, not a MIDI device, to the app.** Keys go to whichever window has focus, just like a real keyboard, so the right app needs to be in front.
- **Incoming MIDI doesn't affect HID buttons.** The host can't sync their LEDs.
