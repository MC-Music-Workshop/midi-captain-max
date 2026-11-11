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

HID has no MIDI channel. The button's **Channel** field is ignored, and HID messages in lists don't show one.

## Actions

| Action | What it does | Use it for |
|---|---|---|
| **Send** | presses and releases the key right away, like a quick tap | almost everything: shortcuts, page turns, transport |
| **Press** | presses the key and keeps it down | holding a key, or dragging with the mouse |
| **Release** | lets go of a key you pressed with **Press**, and of its modifier if you set the same one here. Key `all` lets go of every key, modifier and mouse button | ending a **Press** |
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

Modifiers apply to keyboard keys only. With `Mouse_L` or `Mouse_R` the modifier is ignored, so Shift-click and Ctrl-click aren't possible.

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

A button with **Type** set to **HID** sends its action **when you press it**. Lifting your foot sends nothing. **Mode** changes what the LED does, and which **Also send** list goes out:

| Mode | Each press | LED | Also send |
|---|---|---|---|
| **Toggle** (default) | sends the action | turns on and off on alternate presses | alternates between the **when turned on** and **when turned off** lists, like the LED |
| **Momentary** | sends the action | flashes briefly | sends its one list every press |
| **Keytimes (short/long)** | the entries decide | the entries decide | not used: put messages in the entries |

If you want the same extras on every press, use **Momentary**.

**Momentary** doesn't hold the key while your foot is down. To do that, use **Keytimes**, below.

A **Delay** on its own doesn't light the LED, since nothing visible happened. It doesn't turn a **Toggle** button on or off either, so every press sends the **when turned on** list and the **when turned off** list never goes out.

## HID in message lists

HID also works anywhere you can add messages:

- **Also send** on any button, after the button's own message. See [Multiple Messages](./multiple-messages.md).
- **Keytimes** entries, on press or release, for taps or holds. See [Keytimes](./keytimes.md).

In a list, pick **HID** as the message type. The **Action**, **Key**, **Modifier** and **Delay ms** fields work as above, with lowercase option names: `send`, `press`, `release`, `delay`, and modifiers `ctrl`, `shift`, `alt`, `option`, `windows`. On a Mac, Command is `windows`. Messages go out in the order listed, which is what makes **Press**, **Delay** and **Release** useful.

## Examples

**Turn sheet-music pages.** Two buttons, both **Type** HID, **Mode** Momentary: one with key `Right`, one with key `Left`. Many score readers and PDF viewers also take `PageDown` / `PageUp`.

**Save in a DAW.** **Type** HID, key `S`. Modifier **Ctrl** on Windows, **Windows (⊞)** for ⌘S on a Mac.

**Hold a key while your foot is down** (push-to-talk, a held mouse click). Set **Mode** to **Keytimes (short/long)**, then:

1. Add one **Short Press Cycle** entry. In **short_down**, add HID **Press** with your key and modifier. In **short_up**, add HID **Release** with the same key and the same modifier.
2. Add one **Long Press Cycle** entry. In **long_up**, add the same HID **Release**.

A quick tap releases through **short_up**. Holding past the long-press threshold skips **short_up**, so the long entry's **long_up** releases instead. Without it, a long hold leaves the key stuck down.

The modifier matters: a **Release** without one lets go of the key but leaves the modifier down, so **Press** Ctrl+A followed by **Release** A leaves Ctrl held. If nothing else should stay held, **Release** with key `all` in both places is simpler: it lets go of every key, modifier and mouse button.

Don't change pages while holding. If the page changes before you lift your foot (another switch's page button, or the host jumping pages), the pedal ignores that switch until it's released, so neither **short_up** nor **long_up** fires and the key stays down. A button with **Release** and key `all` clears it.

**Two keys in a row.** **Type** HID, **Mode** Momentary, key `Esc`. Under **Also send**, add HID **Delay** of 100 ms, then HID **Send** with key `Space`. One press sends Esc, waits, then sends Space.

## Things to know

- **Keys are sent by their position on a US keyboard.** The computer maps them through its own keyboard layout, so on a German (QWERTZ) layout `Y` types Z, and on a French (AZERTY) layout `A` types Q.
- **The pedal is a keyboard, not a MIDI device, to the app.** Keys go to whichever window has focus, just like a real keyboard, so the right app needs to be in front.
- **Incoming MIDI doesn't affect HID buttons.** The host can't sync their LEDs.
