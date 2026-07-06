# Issue #15 P2 — Firmware Runtime Page Switching Implementation Plan

**Status:** Shipped — runtime page switching is on `main`; #15 (Pages parity) remains open for later phases.
> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a runtime `switch_page(n)` to the firmware that re-renders the active page (buttons, LEDs, screen, encoder, expression) in RAM, plus per-page MIDI-channel resolution — without the device ever writing the config file.

**Architecture:** Split `code.py` boot init into *one-time* (hardware, fonts, display objects) vs *per-page* (a new `switch_page(n)` function). Boot calls `switch_page(active_page)` once; the same function is reachable from the serial REPL for testing. Per-page MIDI channel resolution (button → page → device) is baked at config-validation time in `core/config.py`, so no runtime channel logic is needed.

**Tech Stack:** CircuitPython 7.x (RP2040), Python 3 + pytest (desktop, with hardware mocks in `tests/mocks/`). Design doc: `docs/plans/2026-06-25-issue-15-P2-firmware-page-switch-design.md`.

**Locked decisions (from design doc):** reset-on-entry state; REPL-only invocation (triggers are P3); channel-only override (per-page `display` deferred to P4); PC patch memory (`pc_values[]`) carries across switches.

---

## Background the implementer needs

- **`core/config.py` is desktop-testable** (pytest, with `tests/mocks/`). `code.py` is the on-device boot script and is **not** import-tested — it runs hardware init at module scope. So: pure logic → `core/config.py` with pytest; `switch_page` → `code.py`, verified on-device via the serial REPL.
- **Channel is baked at validation time.** `validate_button(btn, i, global_channel)` (`core/config.py:269`) writes `"channel": btn.get("channel", default_channel)` into every button (`config.py:336`). `validate_config` (`config.py:439–453`) loops pages and currently passes the **top-level** `global_channel` to every page's buttons. After validation each button has an explicit `channel`, so `code.py`'s runtime `btn_config.get("channel", 0)` always finds it. **This is why per-page channel resolution belongs in `validate_config`, not `switch_page`.**
- **Per-page state arrays never resize.** All pages share the device's fixed `BUTTON_COUNT` (P1 validators enforce per-page button count). `switch_page` rebuilds array *contents*, never lengths.
- **Display objects are created once.** `button_labels[]`, `button_boxes[]`, `status_label`, `exp1/2_label` are built in the `HAS_TFT` block (`code.py:541–648`). On switch we mutate their `.text`/`.color`/palette in place — never recreate (RAM fragmentation on RP2040).
- **Read AGENTS.md (firmware) CP 7.x syntax restrictions** before writing any code: no walrus, no `match`, no dict-unpacking literals, no f-string `!r`/`!s`/`!a`, no `str.isalnum/isalpha/isdigit`. CI greps for these.

---

## Task 1: Per-page MIDI channel resolution (button → page → device)

**Files:**
- Modify: `firmware/dev/core/config.py:439-453` (the page loop in `validate_config`)
- Test: `firmware/dev/tests/test_config.py` (add to existing `TestToPages` area or a new `TestPerPageChannel` class)

**Why:** A page may set its own `global_channel`; its buttons (without an explicit `channel`) should fall back to the page value, then the device value. Confined to `validate_config` so runtime + `switch_page` need zero channel logic.

**Step 1: Write the failing test**

Add to `firmware/dev/tests/test_config.py`:

```python
class TestPerPageChannel:
    def test_button_falls_back_to_page_global_channel(self):
        # device default 0, page overrides to 5, button has no explicit channel
        cfg = {
            "global_channel": 0,
            "pages": [
                {"global_channel": 5, "buttons": [{"label": "A", "cc": 20}]},
            ],
        }
        out = validate_config(cfg, button_count=1)
        assert out["pages"][0]["buttons"][0]["channel"] == 5

    def test_button_explicit_channel_wins_over_page(self):
        cfg = {
            "global_channel": 0,
            "pages": [
                {"global_channel": 5, "buttons": [{"label": "A", "cc": 20, "channel": 9}]},
            ],
        }
        out = validate_config(cfg, button_count=1)
        assert out["pages"][0]["buttons"][0]["channel"] == 9

    def test_page_without_override_uses_device_channel(self):
        cfg = {
            "global_channel": 3,
            "pages": [{"buttons": [{"label": "A", "cc": 20}]}],
        }
        out = validate_config(cfg, button_count=1)
        assert out["pages"][0]["buttons"][0]["channel"] == 3

    def test_invalid_page_channel_falls_back_to_device(self):
        # out-of-range / non-int page channel ignored, device value used
        cfg = {
            "global_channel": 2,
            "pages": [{"global_channel": 99, "buttons": [{"label": "A", "cc": 20}]}],
        }
        out = validate_config(cfg, button_count=1)
        assert out["pages"][0]["buttons"][0]["channel"] == 2
```

**Step 2: Run to verify failure**

Run: `cd firmware/dev && python3 -m pytest tests/test_config.py::TestPerPageChannel -v`
Expected: FAIL — buttons get `0`/`3`/`2` from the device-level channel, page override `5` ignored (and the explicit-channel test may already pass).

**Step 3: Implement**

In `firmware/dev/core/config.py`, inside the `for page in cfg.get("pages", []):` loop (currently ~439-448), resolve a per-page effective channel **before** validating that page's buttons:

```python
    for page in cfg.get("pages", []):
        if not isinstance(page, dict):
            page = {}
        # Per-page global_channel override (button -> page -> device).
        page_channel = page.get("global_channel", global_channel)
        if not isinstance(page_channel, int) or page_channel < 0 or page_channel > 15:
            page_channel = global_channel
        buttons = list(page.get("buttons", []))
        while len(buttons) < button_count:
            buttons.append({})
        validated_buttons = [
            validate_button(btn, i, page_channel) for i, btn in enumerate(buttons[:button_count])
        ]
        new_page = {}
        for k, v in page.items():
            new_page[k] = v
        new_page["buttons"] = validated_buttons
        validated_pages.append(new_page)
```

(Note `bool` is an `int` subclass; the range check `0 <= x <= 15` admits `True`==1/`False`==0 — acceptable here, matches existing device-level handling at `config.py:434`. Do not add special bool handling unless a test demands it.)

**Step 4: Run to verify pass**

Run: `cd firmware/dev && python3 -m pytest tests/test_config.py::TestPerPageChannel -v`
Expected: PASS (4 passed).

**Step 5: Full Python suite (no regressions)**

Run: `cd firmware/dev && python3 -m pytest tests/ -q`
Expected: all pass (P1 baseline was 581).

**Step 6: Commit**

```bash
git add firmware/dev/core/config.py firmware/dev/tests/test_config.py
git commit -m "Resolve per-page global_channel in validate_config (button -> page -> device)

Bakes each page's effective MIDI channel into its buttons at validation
time, so runtime page switching needs no channel logic. #15 P2.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Decision — encoder/expression channel fallback

**Files:** none yet (decision gate before Task 3).

**The gap:** `code.py` reads encoder/expression channel directly from the raw active page (`code.py:477` `ENC_CHANNEL = enc_config.get("channel", 0)`, similarly `EXP1/2_CHANNEL` at 494-495) — defaulting to `0`, **not** the device/page `global_channel`. (The `get_encoder_config`/`get_expression_config` helpers in `config.py:509-576` *do* resolve `global_channel`, but `code.py` bypasses them.) This is pre-existing, not introduced by pages.

**Choices:**
- **(A) Align (recommended):** in `switch_page`, default encoder/expression channel to the page's effective channel instead of `0` — makes channel resolution coherent across buttons + encoder + expression. Small, and the natural place is the new code anyway. Behavior change: an encoder with no explicit channel now follows `global_channel` rather than always Ch 1.
- **(B) Preserve:** keep the `0` default for encoder/expression; per-page channel applies to buttons only. Zero behavior change beyond pages, but leaves the inconsistency.

**Action:** Confirm A or B with the maintainer before Task 3. Default to **A** unless told otherwise. The plan below assumes **A** and isolates it to one line per channel inside `switch_page` (Task 3, Step 3) — trivial to drop if B is chosen.

---

## Task 3: Extract per-page boot init into `switch_page(n)` (the core refactor)

**Files:**
- Modify: `firmware/dev/code.py` — move the per-page module-scope blocks into a function; call it once at boot.

**This is the heart of P2. Not pytest-coverable (`code.py` is the on-device boot script). Verified on-device in Task 4.** Work in small sub-steps, running the CP parse check after each (Step "P" below) — a `SyntaxError` here bricks boot.

**Current per-page blocks to relocate (verify line numbers before editing — they shift as you edit):**
- `active_page` / `buttons` derivation — `code.py:282-284`
- Encoder constants `CC_ENCODER`…`ENC_STEPS` — `code.py:465-485`
- Expression config + `CC_EXP1/2`, `EXP1/2_CHANNEL` — `code.py:487-495`
- `button_states[]` build — `code.py:502-508`
- `keytimes_states[]` build — `code.py:510-521`
- `pc_flash_timers`/`hid_flash_timers` reset — `code.py:524-525` (keep `pc_values` one-time, see below)
- `encoder_value`/`encoder_slot` — `code.py:528-529`
- Per-button display label/box **text+color** update — derived from `code.py:574-614` (the *creation* stays one-time; only the per-button `.text`/palette assignment moves into switch)
- Expression label text — `code.py:628-646` (creation one-time; `.text` update moves into switch)
- `init_leds()` call

**Stays one-time at module scope (do NOT move):** hardware objects, fonts, `display_config`, `pc_values = [0]*16`, MIDI thru flags, the `displayio.Group`/`Bitmap`/`TileGrid`/`Label` **object creation**.

**Step 1: Add module-global declarations + the function skeleton**

Place `switch_page` **after** the display-object creation block (after `code.py:648`, `display.show(main_group)`) and after `init_leds`/`set_button_state`/`update_select_group` are defined — i.e. after `code.py:818`. It must reassign module globals, so it needs a `global` declaration listing every name it rebinds.

```python
def switch_page(n):
    """Switch the active page in RAM and re-render everything page-dependent.

    Device never writes config to disk; this only mutates RAM. Reset-on-entry:
    button/keytimes/encoder state rebuild from config defaults (latches/cycles
    are NOT preserved across switches). pc_values[] (patch memory) is NOT reset.
    """
    global active_page, buttons
    global CC_ENCODER, CC_ENCODER_PUSH, ENC_MIN, ENC_MAX, ENC_INITIAL
    global ENC_ENABLED, ENC_PUSH_ENABLED, ENC_PUSH_MODE, ENC_CHANNEL
    global ENC_PUSH_CHANNEL, ENC_PUSH_CC_ON, ENC_PUSH_CC_OFF, ENC_STEPS
    global enc_config, enc_push_config
    global exp_config, exp1_config, exp2_config, CC_EXP1, CC_EXP2, EXP1_CHANNEL, EXP2_CHANNEL
    global button_states, keytimes_states, encoder_value, encoder_slot
    # ... body added in following steps
```

**Step P (run after EACH sub-step below):**
Run: `python3 -m mpy_cross firmware/dev/code.py -o /dev/null` *(or whatever the CI "CircuitPython parse check" invokes — see `.github/workflows/ci.yml`)*.
Expected: no `SyntaxError`. If mpy-cross isn't installed locally, at minimum run `python3 -m py_compile firmware/dev/code.py` (catches plain syntax) and rely on CI for CP-specifics.

**Step 2: Move active-page + buttons + encoder + expression derivation into the body**

Cut `code.py:282-284` and `465-495` content into `switch_page`, prefixing the page resolve with the clamp:

```python
    active_page = get_active_page(config)   # already clamps; re-resolve from config["active_page"]
    config["active_page"] = n               # set by caller-clamped n; see Step 6 for clamp ownership
    buttons = active_page.get("buttons", [])

    enc_config = active_page.get("encoder", {"enabled": True, "cc": 11, "label": "ENC", "min": 0, "max": 127, "initial": 64})
    enc_push_config = enc_config.get("push", {"enabled": True, "cc": 14, "label": "PUSH", "mode": "momentary"})
    CC_ENCODER = enc_config.get("cc", 11)
    # ... (all ENC_* lines verbatim from 469-485)
    exp_config = active_page.get("expression", {})
    exp1_config = exp_config.get("exp1", {...})   # verbatim from 489
    exp2_config = exp_config.get("exp2", {...})   # verbatim from 490
    CC_EXP1 = exp1_config.get("cc", 12)
    CC_EXP2 = exp2_config.get("cc", 13)
```

For the channel lines, apply the Task-2 decision (default **A**):

```python
    _page_channel = active_page.get("global_channel", config.get("global_channel", 0))
    if not isinstance(_page_channel, int) or _page_channel < 0 or _page_channel > 15:
        _page_channel = config.get("global_channel", 0)
    ENC_CHANNEL = enc_config.get("channel", _page_channel)        # A: was `0`
    ENC_PUSH_CHANNEL = enc_push_config.get("channel", _page_channel)
    EXP1_CHANNEL = exp1_config.get("channel", _page_channel)
    EXP2_CHANNEL = exp2_config.get("channel", _page_channel)
```

**Important ordering:** `n`/`active_page` must be resolved at the *top* of the function. The clamp lives with the caller (Step 6) so `config["active_page"]` is already valid; `get_active_page` re-clamps defensively.

Run Step P.

**Step 3: Move state-array + display-text rebuild into the body**

Append to `switch_page`:

```python
    # Rebuild per-button state from config defaults (reset-on-entry).
    button_states = []
    for i in range(BUTTON_COUNT):
        btn_config = buttons[i] if i < len(buttons) else {}
        button_states.append(ButtonState(
            cc=btn_config.get("cc", 0),
            mode=btn_config.get("mode", "toggle"),
            keytimes=btn_config.get("keytimes", 1),
        ))

    keytimes_states = [None] * BUTTON_COUNT
    for i in range(BUTTON_COUNT):
        _kt_cfg = buttons[i] if i < len(buttons) else {}
        if _kt_cfg.get("mode") == "keytimes":
            _kt_threshold = get_long_press_threshold_ms(config, _kt_cfg)
            keytimes_states[i] = KeytimesButtonState(
                _kt_threshold, len(_kt_cfg.get("short", [])), len(_kt_cfg.get("long", [])))

    for i in range(BUTTON_COUNT):
        pc_flash_timers[i] = 0.0       # in-place: pc_flash_timers stays one-time-allocated
        hid_flash_timers[i] = 0.0
    encoder_value = ENC_INITIAL
    encoder_slot = -1

    # Update display text/color in place (objects created once at boot).
    if HAS_TFT:
        for i in range(BUTTON_COUNT):
            btn_config = buttons[i] if i < len(buttons) else {"label": str(i + 1), "color": "white"}
            color_rgb = get_color(btn_config.get("color", "white"))
            off_color = get_off_color_for_display(color_rgb, btn_config.get("off_mode", "dim"))
            button_labels[i].text = btn_config.get("label", str(i + 1))[:6]
            button_labels[i].color = rgb_to_hex(off_color)
            _, box_palette = button_boxes[i]
            box_palette[1] = rgb_to_hex(off_color)
        if HAS_EXPRESSION and exp1_label is not None:
            exp1_label.text = exp1_config.get("label", "EXP1") + ": ---"
            exp2_label.text = exp2_config.get("label", "EXP2") + ": ---"

    init_leds()
```

Notes:
- `pc_flash_timers`/`hid_flash_timers` are reset **in place** (loop-assign) so they don't need `global` (mutating, not rebinding). `button_states`/`keytimes_states` are **rebound** (new list) so they DO need `global` (already declared Step 1).
- The expression label text uses `+ ": ---"` (string concat) — keep it CP-safe; the original used an f-string (`code.py:631`), which is fine too, but avoid `!r`/`!s` specifiers.
- `init_leds()` repaints from rebuilt `button_states` (all off/default) — correct under reset-on-entry. (If per-page preservation ever lands, this is where select-mode repaint-from-state would branch — see AGENTS.md firmware ~256.)

Run Step P.

**Step 4: Delete the now-moved module-scope blocks**

Remove the original inline blocks (282-284, 465-495, 502-529 except `pc_values`/`PC_FLASH_DURATION_MS`, and the per-button text/color *assignments* inside 574-614 / 628-646 — but KEEP the object-creation lines: `displayio.Bitmap`, `TileGrid`, `Label(...)`, `.append(...)`). The creation loop still needs *some* text/color to instantiate labels; leave its initial values as-is (they'll be overwritten by `switch_page` at boot). Simplest: leave 574-646 object creation fully intact, and let `switch_page` overwrite text/color — i.e. you only delete 282-284, 465-495, 502-529 (minus `pc_values`).

Run Step P.

**Step 5: Move `init_leds()`'s original call site**

Find the boot-time `init_leds()` call (`code.py:1427`) and remove it — `switch_page` now owns the initial paint. (Confirm there's no other dependency on that exact call ordering vs. `display.show`.)

**Step 6: Call `switch_page` once at boot with a clamp**

Where the per-page block used to start (right after `display.show(main_group)` / after `switch_page` is defined and `init_leds` exists), add the boot invocation. Clamp ownership lives here so REPL callers and P3 triggers share it:

```python
def _clamp_page(n):
    pages = config.get("pages", [])
    if not pages:
        return 0
    if not isinstance(n, int) or isinstance(n, bool):
        return 0
    return max(0, min(n, len(pages) - 1))

switch_page(_clamp_page(config.get("active_page", 0)))
```

And change `switch_page`'s top to trust the clamped `n`:
```python
    config["active_page"] = _clamp_page(n)
    active_page = get_active_page(config)
    buttons = active_page.get("buttons", [])
```
(`get_active_page` reads `config["active_page"]` and re-clamps — belt and suspenders.)

Run Step P.

**Step 7: Commit**

```bash
git add firmware/dev/code.py
git commit -m "Extract per-page boot init into switch_page(n) for runtime page switching

Splits code.py boot into one-time (hardware/fonts/display objects) vs
per-page (switch_page). Boot calls switch_page once; reachable from REPL
for testing. Reset-on-entry; pc_values carries across; encoder/expression
channel now follows page->device global_channel. #15 P2.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: On-device verification (REPL)

**No pytest coverage possible for `switch_page`.** Verify on hardware (STD10 preferred — exercises encoder + expression; also smoke-test a no-encoder device like Mini6/NANO4).

**Prereq:** a multi-page `config.json` on the device. Create a 2-page test config: page 0 with distinct labels/colors/CCs, page 1 visibly different (e.g. different labels, a different `global_channel`, different encoder CC). Hand-edit on the mounted drive (dev_mode or Switch-1-held boot).

**Step 1: Boot clean**
Power on, open serial. Expected: boots to page 0, screen shows page-0 labels, LEDs page-0 colors. No tracebacks. Confirms the refactor didn't break single-page boot.

**Step 2: Switch via REPL**
Ctrl-C to halt, send a sacrificial CRLF (AGENTS.md serial gotcha), then:
```
>>> switch_page(1)
```
Expected: screen labels change to page 1, LEDs repaint page-1 colors, no traceback. Press a button — verify it sends page-1's CC on page-1's channel (MIDI monitor).

**Step 3: Switch back — reset-on-entry**
On page 1, flip a toggle/latch button (LED on). Then:
```
>>> switch_page(0)
>>> switch_page(1)
```
Expected: returning to page 1 shows the toggle **off** (state reset, not preserved). Confirms reset-on-entry.

**Step 4: PC carry-across**
On page 0, press a `pc`/`pc_inc` button to set a patch. `switch_page(1)`, press a `pc_inc` button on the same channel. Expected: it increments from the page-0 value (memory carried), not from 0.

**Step 5: Clamp safety**
```
>>> switch_page(99)
>>> switch_page(-1)
```
Expected: clamps to last/first page, no crash.

**Step 6: Encoder/expression (STD10)**
After `switch_page(1)`, turn the encoder — verify it sends page-1's encoder CC/channel/range. Move expression pedals — verify page-1 labels + CCs.

**Step 7: Full repo gate**
Run: `./tools/test-all.sh`
Expected: green (same baseline as P1 — the types.generated git-diff check passes once committed).

**Step 8: Record results** in the session file and the PR body (per `feedback_pr_test_recording`): which device(s), which steps passed, observed MIDI.

---

## Out of scope (do NOT build)
- Switch triggers (press-timing inc/dec, MIDI-IN CC jump) — **P3**.
- Per-page `display` override / font reload on switch — **P4**.
- `pc_carryover` config toggle — future (one-line seam already at the `pc_values`-not-reset point).
- Per-page state preservation ("remember" latches/cycles) — future (global toggle + per-page override).
- Editor UI for pages — **P4**.

## Deferred P1 review items to revisit in P4 (not P2)
- #5 `PAGE_SCOPED_PATH` regex generalization, #6 client validates active page only, #8 per-page `global_channel`/`Page.name` validated only in Rust. See session file.
