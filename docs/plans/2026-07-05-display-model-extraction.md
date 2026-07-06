# Display Model Extraction Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Date:** 2026-07-05
**Status:** Implemented (2026-07-06) — `core/display_model.py` extracted (`compute_layout`, `button_visual`, `keytimes_visual`, `build_screen`) with 20 pytest cases (`tests/test_display_model.py`), first coverage of the #143/#157 label/color rules. `code.py` builds its TFT from the model (init, `set_button_state`, `_render_keytimes_led`, page-switch relabel); the web demo's `PY_GLUE` dropped its duplicated render rules for `keytimes_visual`; the hero gained a live 240×240 `<canvas>` TFT rendered from the same model. pytest 672 green (incl. 20 new display_model cases), CP-7 parse clean, ruff clean. **Remaining:** on-device flash check (Task 5 Step 6) is the user's gate before merge. (`test-all.sh`'s Rust phase is unrelated-red in this worktree — missing staged `circuitpython/*.uf2` resource, not touched by this work.)

**Goal:** Extract the TFT screen's layout and color/text decision logic from `code.py` into a pure `firmware/dev/core/display_model.py`, so the firmware TFT, the home-page browser demo (via the existing MicroPython wasm engine), and pytest all consume the same screen model — zero drift by construction, same pattern as `core/button.py`.

**Architecture:** `display_model.py` exposes pure functions: `compute_layout()` (geometry per device), `button_visual()` (on/off label+box colors), `keytimes_visual()` (the #143/#157 last-fired label/color rules currently inlined in `code.py` *and* duplicated in the web page's Python glue), and `build_screen()` (full initial draw model). `code.py` keeps its displayio objects but builds/updates them from these functions. The web page loads `display_model.py` into the wasm engine alongside `button.py`/`colors.py` and blits the returned model onto a 240×240 `<canvas>` in the hero device. New pytest module covers geometry and the label rules (currently untested — they live only in `code.py`).

**Tech Stack:** CircuitPython-7-compatible Python (must pass `tools/check-circuitpython-parse.sh` — no walrus/match), pytest, MicroPython wasm (already vendored), canvas 2D.

---

## Context for a fresh engineer

- **The pattern to copy:** `firmware/dev/core/button.py` is pure (no hardware imports), tested in `tests/test_press_tracker.py` etc., and executed verbatim in the browser: `site/index.html`'s `bootFirmwareEngine()` fetches `site/firmware/*.py` (copies refreshed by `tools/sync-site-firmware.sh`) into a MicroPython wasm runtime and calls it via JSON-string glue (`PY_GLUE` in `index.html`). This plan does the same for the screen.
- **Where the display logic lives today** (all in `firmware/dev/code.py`):
  - Geometry + initial build: lines ~520-640 (`if HAS_TFT:` block — box bitmaps, `label.Label`s, status at (120,120), expression labels at (70,150)/(170,150)).
  - On/off visual update: `set_button_state()` display half (~lines 725-756).
  - Keytimes label text + color rules: `_render_keytimes_led()` (~lines 1190-1210) — the `last_fired` gating, label fallback chain, and black→button-color fallback (#143/#157).
  - Page-switch label reset: `switch_page()` (~lines 875-884).
- **The duplication being killed:** `site/index.html`'s `PY_GLUE` `_render()` re-implements the `_render_keytimes_led` label/color rules. After this plan, glue calls `display_model.keytimes_visual()` instead.
- **Colors:** `core/colors.py` already has `get_color`, `dim_color`, `rgb_to_hex`, `get_off_color_for_display`, `resolve_keytimes_render_color` — `display_model.py` imports from it (works in wasm: `colors.py` is already loaded there; on-device it's `core.colors`, see the import-shim note in Task 1).
- **Testing:** run `python3 -m pytest tests/ -v` from repo root. Full verification: `./tools/test-all.sh`. CP 7.x syntax guard: `tools/check-circuitpython-parse.sh`.
- **Fonts:** `FONT_SIZE_MAP` in `code.py:72` — heights: small=8, medium=20, large=60. Shipped default config uses `medium` (height 20) for everything. Browser canvas approximates PTSans with a system font; geometry uses the real heights.
- **Device geometry branches** (from `code.py` ~535-565): `button_height = button_font_height + 10`; NANO4 (4 buttons): width 100, spacing 120, row_size 2; Mini6 (6): width 70, spacing 80, row_size 3; STD10 (10): width 46, spacing 48, row_size 5. Top row y=5; bottom row y=240−height−5; x = 1 + col*spacing. Labels centered in the box. Screen is 240×240 (ST7789).

---

### Task 1: `compute_layout()` — geometry per device

**Files:**
- Create: `firmware/dev/core/display_model.py`
- Create: `tests/test_display_model.py`

**Step 1: Write the failing tests**

```python
"""Tests for core/display_model.py — pure screen model shared by firmware TFT,
the browser demo, and these tests."""

import sys
from pathlib import Path

FIRMWARE_DIR = Path(__file__).parent.parent / "firmware" / "dev"
sys.path.insert(0, str(FIRMWARE_DIR))

from core.display_model import compute_layout


class TestComputeLayout:
    def test_std10_geometry(self):
        lo = compute_layout(button_count=10, button_font_height=20)
        assert lo["button_width"] == 46
        assert lo["button_height"] == 30          # font 20 + 10 padding
        assert lo["row_size"] == 5
        # First button, top row
        assert lo["positions"][0] == (1, 5)
        # Second button steps by spacing 48
        assert lo["positions"][1] == (49, 5)
        # Sixth button starts the bottom row: y = 240 - 30 - 5
        assert lo["positions"][5] == (1, 205)

    def test_mini6_geometry(self):
        lo = compute_layout(button_count=6, button_font_height=20)
        assert lo["button_width"] == 70
        assert lo["row_size"] == 3
        assert lo["positions"][3] == (1, 205)     # bottom row starts at index 3

    def test_nano4_geometry(self):
        lo = compute_layout(button_count=4, button_font_height=20)
        assert lo["button_width"] == 100
        assert lo["row_size"] == 2
        assert lo["positions"][1] == (121, 5)     # spacing 120

    def test_label_centers(self):
        lo = compute_layout(button_count=10, button_font_height=20)
        # Centered in the box: x + w//2, y + h//2
        assert lo["centers"][0] == (1 + 46 // 2, 5 + 30 // 2)
```

**Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_display_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.display_model'`

**Step 3: Write the implementation**

`firmware/dev/core/display_model.py`:

```python
"""
Pure screen model for the TFT display (ST7789 240x240).

No displayio, no hardware — code.py builds its displayio objects from this
model, the home-page browser demo runs it in MicroPython wasm to draw the
same screen on a canvas, and tests/test_display_model.py asserts on it
directly. Same zero-drift pattern as core/button.py.

CircuitPython 7.x compatible (guarded by tools/check-circuitpython-parse.sh).
"""

# Import shim: on-device the package is core.colors; in the browser wasm
# runtime the files sit flat (colors.py next to display_model.py).
try:
    from core.colors import (get_color, rgb_to_hex, get_off_color_for_display,
                             resolve_keytimes_render_color)
except ImportError:
    from colors import (get_color, rgb_to_hex, get_off_color_for_display,
                        resolve_keytimes_render_color)

SCREEN_SIZE = (240, 240)


def compute_layout(button_count, button_font_height):
    """Per-device screen geometry. Mirrors the branches formerly in code.py.

    Returns a dict:
        button_width, button_height, button_spacing, row_size,
        positions: [(x, y)] per button (box top-left),
        centers:   [(cx, cy)] per button (label anchor, centered in box).
    """
    button_height = button_font_height + 10  # 10px padding

    if button_count == 4:
        button_width, button_spacing, row_size = 100, 120, 2
    elif button_count == 6:
        button_width, button_spacing, row_size = 70, 80, 3
    else:
        button_width, button_spacing, row_size = 46, 48, 5

    top_row_y = 5
    bottom_row_y = SCREEN_SIZE[1] - button_height - 5

    positions = []
    centers = []
    for i in range(button_count):
        col = i if i < row_size else i - row_size
        x = 1 + col * button_spacing
        y = top_row_y if i < row_size else bottom_row_y
        positions.append((x, y))
        centers.append((x + button_width // 2, y + button_height // 2))

    return {
        "button_width": button_width,
        "button_height": button_height,
        "button_spacing": button_spacing,
        "row_size": row_size,
        "positions": positions,
        "centers": centers,
    }
```

**Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_display_model.py -v`
Expected: 4 PASS

**Step 5: Commit**

```bash
git add firmware/dev/core/display_model.py tests/test_display_model.py
git commit -m "Extract TFT geometry into pure core/display_model.py: compute_layout() with per-device tests"
```

---

### Task 2: `button_visual()` — on/off label + box colors

Mirrors the display half of `set_button_state()` (`code.py` ~725-756): on = full button color; off = `get_off_color_for_display` (always dim so labels stay legible, regardless of `off_mode`).

**Files:**
- Modify: `firmware/dev/core/display_model.py`
- Modify: `tests/test_display_model.py`

**Step 1: Write the failing tests**

```python
from core.display_model import button_visual


class TestButtonVisual:
    def test_on_uses_full_color(self):
        v = button_visual({"color": "green"}, on=True)
        assert v == {"label_color": 0x00FF00, "box_color": 0x00FF00}

    def test_off_uses_dim_color(self):
        # dim_color factor 0.15: 255 -> 38 = 0x26
        v = button_visual({"color": "green"}, on=False)
        assert v == {"label_color": 0x002600, "box_color": 0x002600}

    def test_off_mode_off_still_dims_display(self):
        # get_off_color_for_display ignores off_mode — labels stay visible
        v = button_visual({"color": "green", "off_mode": "off"}, on=False)
        assert v["label_color"] == 0x002600

    def test_missing_color_falls_back_white(self):
        v = button_visual({}, on=True)
        assert v["label_color"] == 0xFFFFFF
```

**Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_display_model.py::TestButtonVisual -v`
Expected: FAIL with `ImportError: cannot import name 'button_visual'`

**Step 3: Write the implementation** (append to `display_model.py`)

```python
def button_visual(btn_config, on):
    """Label + box colors for a plain (non-keytimes) button's display state.

    Off state always renders the dimmed color (never fully off) so labels
    stay legible — mirrors get_off_color_for_display's contract.

    Returns {"label_color": 0xRRGGBB, "box_color": 0xRRGGBB}.
    """
    color_rgb = get_color(btn_config.get("color", "white"))
    off_mode = btn_config.get("off_mode", "dim")
    rgb = color_rgb if on else get_off_color_for_display(color_rgb, off_mode)
    hex_color = rgb_to_hex(rgb)
    return {"label_color": hex_color, "box_color": hex_color}
```

**Note:** `set_button_state()` today supports keytime-indexed colors via `get_button_color(btn_config, keytime)`. That helper stays in `code.py` (it needs `get_button_state_config`); `code.py` will pass the resolved config dict in — see Task 5. If that proves awkward, add a `color_name` parameter instead; do NOT copy `get_button_state_config` into display_model.

**Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_display_model.py -v`
Expected: all PASS

**Step 5: Commit**

```bash
git add firmware/dev/core/display_model.py tests/test_display_model.py
git commit -m "display_model.button_visual(): on/off label+box colors extracted from set_button_state"
```

---

### Task 3: `keytimes_visual()` — last-fired label/color rules (#143/#157)

This is the heart of the extraction: the rules currently inlined in `_render_keytimes_led()` (`code.py` ~1190-1210) **and duplicated** in `site/index.html`'s `PY_GLUE` `_render()`. First test coverage these rules ever get.

**Files:**
- Modify: `firmware/dev/core/display_model.py`
- Modify: `tests/test_display_model.py`

**Step 1: Write the failing tests**

```python
from core.button import KeytimesButtonState
from core.display_model import keytimes_visual


def _kt_state(**kw):
    st = KeytimesButtonState(threshold_ms=500, short_length=2, long_length=2)
    for k, v in kw.items():
        setattr(st, k, v)
    return st


class TestKeytimesVisual:
    CFG = {"label": "VERB", "color": "white", "mode": "keytimes"}

    def test_before_first_press_shows_button_label_and_color(self):
        v = keytimes_visual(_kt_state(), self.CFG)
        assert v["text"] == "VERB"
        assert v["box_color"] == 0xFFFFFF      # falls back to button color
        assert v["label_color"] == 0xFFFFFF

    def test_short_fired_shows_short_label_and_color(self):
        st = _kt_state(last_fired="short", short_color="green", short_label="ON")
        v = keytimes_visual(st, self.CFG)
        assert v["text"] == "ON"
        assert v["box_color"] == 0x00FF00

    def test_long_label_falls_back_to_short_then_button(self):
        # 143: a labelless long entry shows the prior short label
        st = _kt_state(last_fired="long", short_label="ON")
        v = keytimes_visual(st, self.CFG)
        assert v["text"] == "ON"
        st2 = _kt_state(last_fired="long")
        assert keytimes_visual(st2, self.CFG)["text"] == "VERB"

    def test_last_fired_short_suppresses_stale_long_color(self):
        # 157: long color must not stick once a short press fires
        st = _kt_state(last_fired="short", short_color="green",
                       long_color="magenta")
        v = keytimes_visual(st, self.CFG)
        assert v["box_color"] == 0x00FF00

    def test_long_overlay_keeps_long_color_over_short(self):
        cfg = dict(self.CFG, long_overlay=True)
        st = _kt_state(last_fired="short", short_color="green",
                       long_color="magenta")
        assert keytimes_visual(st, cfg)["box_color"] == 0xFF00FF

    def test_kill_switch_black_label_falls_back_to_button_color(self):
        # 143: black-on-black guard — label color falls back to button color
        st = _kt_state(last_fired="short", short_color="off")
        v = keytimes_visual(st, self.CFG)
        assert v["box_color"] == 0x000000       # LED/box genuinely off
        assert v["label_color"] == 0xFFFFFF     # label stays legible

    def test_dim_stripped_from_label_color(self):
        # 143: label color renders at full brightness even for dim entries
        st = _kt_state(last_fired="short", short_color="green", short_dim=True)
        v = keytimes_visual(st, self.CFG)
        assert v["box_color"] == 0x002600       # box honors dim
        assert v["label_color"] == 0x00FF00     # label does not

    def test_label_truncated_to_six_chars(self):
        st = _kt_state(last_fired="short", short_label="LONGLABEL")
        assert keytimes_visual(st, self.CFG)["text"] == "LONGLA"
```

**Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_display_model.py::TestKeytimesVisual -v`
Expected: FAIL with `ImportError: cannot import name 'keytimes_visual'`

**Step 3: Write the implementation** (append to `display_model.py`)

Port the body of `_render_keytimes_led()`'s display section verbatim — do not "improve" it; the point is bit-identical behavior:

```python
def keytimes_visual(state, btn_config):
    """Screen text + colors for a mode:"keytimes" button.

    Extracted from code.py _render_keytimes_led() so firmware, browser demo,
    and tests share the #143/#157 rules:
      - box/LED color: last_fired gates which layer wins (see
        resolve_keytimes_render_color); long_overlay opts into persistence.
      - label text: last fired class owns it; long falls back to short_label
        then the button label; short falls straight to the button label.
      - label color: same resolve at full brightness (dim stripped), with a
        black->button-color fallback so it is never black-on-black.

    Returns {"text": str, "label_color": 0xRRGGBB, "box_color": 0xRRGGBB}.
    """
    long_overlay = btn_config.get("long_overlay", False)

    rgb = resolve_keytimes_render_color(state.last_fired,
                                        state.short_color, state.short_dim,
                                        state.long_color, state.long_dim,
                                        btn_config.get("color"),
                                        long_overlay)

    if state.last_fired == "long":
        text = (state.long_label or state.short_label or btn_config.get("label", ""))[:6]
    elif state.last_fired == "short":
        text = (state.short_label or btn_config.get("label", ""))[:6]
    else:
        text = btn_config.get("label", "")[:6]

    label_rgb = resolve_keytimes_render_color(state.last_fired,
                                              state.short_color, False,
                                              state.long_color, False,
                                              btn_config.get("color"),
                                              long_overlay)
    if not any(label_rgb):
        label_rgb = get_color(btn_config.get("color") or "white")

    return {
        "text": text,
        "label_color": rgb_to_hex(label_rgb),
        "box_color": rgb_to_hex(rgb),
    }
```

Also return the raw LED rgb? No — LED stays with `resolve_keytimes_render_color` at the call site (`code.py` needs the tuple for NeoPixels; browser glue already gets it). YAGNI.

**Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_display_model.py -v`
Expected: all PASS

**Step 5: Commit**

```bash
git add firmware/dev/core/display_model.py tests/test_display_model.py
git commit -m "display_model.keytimes_visual(): #143/#157 label/color rules extracted from _render_keytimes_led, first test coverage"
```

---

### Task 4: `build_screen()` — full initial draw model

**Files:**
- Modify: `firmware/dev/core/display_model.py`
- Modify: `tests/test_display_model.py`

**Step 1: Write the failing tests**

```python
from core.display_model import build_screen


class TestBuildScreen:
    BUTTONS = [{"label": "TSC", "color": "green"},
               {"label": "CHOR", "color": "blue"}]

    def test_screen_shape(self):
        s = build_screen(self.BUTTONS, button_count=10, button_font_height=20,
                         has_expression=False, exp1_label="EXP1", exp2_label="EXP2")
        assert s["size"] == (240, 240)
        assert len(s["buttons"]) == 10
        assert s["status"] == {"x": 120, "y": 120, "text": "Ready",
                               "color": 0xFFFFFF}
        assert s["expression"] == []

    def test_button_entries(self):
        s = build_screen(self.BUTTONS, 10, 20, False, "EXP1", "EXP2")
        b0 = s["buttons"][0]
        assert (b0["x"], b0["y"]) == (1, 5)
        assert (b0["w"], b0["h"]) == (46, 30)
        assert b0["text"] == "TSC"
        assert b0["label_color"] == 0x002600     # boots in off state (dim green)
        # Missing config beyond the provided list falls back to numbered white
        assert s["buttons"][2]["text"] == "3"

    def test_expression_entries(self):
        s = build_screen(self.BUTTONS, 10, 20, True, "VOL", "WAH")
        assert s["expression"][0] == {"x": 70, "y": 150, "text": "VOL: ---",
                                      "color": 0x888888}
        assert s["expression"][1]["text"] == "WAH: ---"

    def test_label_truncation(self):
        s = build_screen([{"label": "LONGLABEL", "color": "red"}], 4, 20,
                         False, "EXP1", "EXP2")
        assert s["buttons"][0]["text"] == "LONGLA"
```

**Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_display_model.py::TestBuildScreen -v`
Expected: FAIL with ImportError

**Step 3: Write the implementation** (append)

```python
STATUS_POS = (120, 120)
EXPRESSION_POS = ((70, 150), (170, 150))


def build_screen(buttons, button_count, button_font_height,
                 has_expression, exp1_label, exp2_label):
    """Initial screen model: every button box+label in its boot (off) state,
    the status line, and expression readouts when the device has pedals.

    Mirrors the HAS_TFT init block formerly in code.py. code.py turns this
    into displayio objects; the browser demo paints it onto a canvas.
    """
    layout = compute_layout(button_count, button_font_height)
    entries = []
    for i in range(button_count):
        btn_config = buttons[i] if i < len(buttons) else {"label": str(i + 1),
                                                          "color": "white"}
        x, y = layout["positions"][i]
        visual = button_visual(btn_config, on=False)
        entries.append({
            "x": x, "y": y,
            "w": layout["button_width"], "h": layout["button_height"],
            "cx": layout["centers"][i][0], "cy": layout["centers"][i][1],
            "text": btn_config.get("label", str(i + 1))[:6],
            "label_color": visual["label_color"],
            "box_color": visual["box_color"],
        })

    expression = []
    if has_expression:
        for pos, lbl in zip(EXPRESSION_POS, (exp1_label, exp2_label)):
            expression.append({"x": pos[0], "y": pos[1],
                               "text": lbl + ": ---", "color": 0x888888})

    return {
        "size": SCREEN_SIZE,
        "buttons": entries,
        "status": {"x": STATUS_POS[0], "y": STATUS_POS[1],
                   "text": "Ready", "color": 0xFFFFFF},
        "expression": expression,
    }
```

**Note:** `code.py`'s init truncates labels at `[:6]` in the Label constructor — keep parity. Its boot state uses `get_off_color_for_display(color, off_mode)` which `button_visual(cfg, on=False)` reproduces.

**Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_display_model.py -v`
Expected: all PASS

**Step 5: Commit**

```bash
git add firmware/dev/core/display_model.py tests/test_display_model.py
git commit -m "display_model.build_screen(): full initial screen model (boxes, labels, status, expression)"
```

---

### Task 5: Refactor `code.py` to consume the model

**Files:**
- Modify: `firmware/dev/code.py` (three sites)

No new behavior — the TFT must render pixel-identically. This task is pure substitution.

**Step 1: Init block (~520-640).** Replace the geometry branches and per-button loop internals with:

```python
from core.display_model import build_screen, keytimes_visual, button_visual
```
(add to the existing `core.*` import block near the top), then in the `if HAS_TFT:` init:

```python
    screen_model = build_screen(buttons, BUTTON_COUNT, BUTTON_FONT_HEIGHT,
                                HAS_EXPRESSION,
                                exp1_config.get("label", "EXP1") if HAS_EXPRESSION else "EXP1",
                                exp2_config.get("label", "EXP2") if HAS_EXPRESSION else "EXP2")
    for b in screen_model["buttons"]:
        box_bitmap = displayio.Bitmap(b["w"], b["h"], 2)
        box_palette = displayio.Palette(2)
        box_palette[0] = 0x000000
        box_palette[1] = b["box_color"]
        for bx in range(b["w"]):
            box_bitmap[bx, 0] = 1
            box_bitmap[bx, b["h"] - 1] = 1
        for by in range(b["h"]):
            box_bitmap[0, by] = 1
            box_bitmap[b["w"] - 1, by] = 1
        box_sprite = displayio.TileGrid(box_bitmap, pixel_shader=box_palette,
                                        x=b["x"], y=b["y"])
        button_boxes.append((box_sprite, box_palette))
        main_group.append(box_sprite)
        lbl = label.Label(BUTTON_FONT, text=b["text"], color=b["label_color"],
                          anchor_point=(0.5, 0.5),
                          anchored_position=(b["cx"], b["cy"]))
        button_labels.append(lbl)
        main_group.append(lbl)
```
Status + expression labels likewise read positions/text/colors from `screen_model["status"]` / `screen_model["expression"]`. Delete the now-dead local geometry variables (`button_width`, `button_spacing`, `row_size`, `top_row_y`, `bottom_row_y`, per-button `x/y` computation) — they live in `compute_layout` now.

**Step 2: `set_button_state()` display half (~745-756).** Replace the color math with `button_visual`. Careful: today it resolves keytime-indexed color first (`get_button_color(btn_config, keytime)`), so pass a config whose color is already resolved:

```python
    if HAS_TFT and idx < len(button_labels):
        resolved = dict(btn_config)
        resolved["color"] = get_button_state_config(btn_config, btn_state.get_keytime()).get("color", "white")
        visual = button_visual(resolved, on)
        button_labels[idx].color = visual["label_color"]
        if idx < len(button_boxes):
            _, box_palette = button_boxes[idx]
            box_palette[1] = visual["box_color"]
```
(Keep the LED half of the function untouched — it uses `get_off_color`, which honors `off_mode`, deliberately different from the display.)

**Step 3: `_render_keytimes_led()` display section (~1190-1210).** Replace the inline label-text/label-color block with:

```python
    if HAS_TFT and idx < len(button_labels):
        visual = keytimes_visual(state, btn_config)
        button_labels[idx].text = visual["text"]
        button_labels[idx].color = visual["label_color"]
        if idx < len(button_boxes):
            _, box_palette = button_boxes[idx]
            box_palette[1] = visual["box_color"]
```
The LED half above it keeps calling `resolve_keytimes_render_color` directly (it needs the rgb tuple). Note `visual["box_color"]` equals the old `rgb_to_hex(rgb)` — same resolve, same inputs.

**Step 4: Verify**

Run: `python3 -m pytest tests/ -v` — all pass (existing suites cover the callers).
Run: `tools/check-circuitpython-parse.sh` — `code.py` + `core/display_model.py` parse clean under CP 7.x rules.
Run: `ruff check firmware/ tests/` — clean (watch for now-unused imports in `code.py`, e.g. if `get_off_color_for_display` no longer has call sites there).

**Step 5: Commit**

```bash
git add firmware/dev/code.py
git commit -m "code.py builds the TFT from display_model: init, set_button_state, and keytimes render all consume the shared screen model"
```

**Step 6 (manual, user-driven):** flash a device via `tools/deploy.sh` and eyeball the screen — do NOT run deploy yourself (user preference: never run deploy.sh on the user's behalf). Ask the user to verify boot screen, toggle a switch, work a keytimes switch.

---

### Task 6: Ship the model to the site + wasm glue

**Files:**
- Modify: `tools/sync-site-firmware.sh` (add `display_model.py`)
- Modify: `.github/workflows/pages.yml` (add path trigger)
- Modify: `site/index.html` (`PY_GLUE`)
- Create (by running the sync script): `site/firmware/display_model.py`

**Step 1:** In `tools/sync-site-firmware.sh`, extend the copy:

```bash
cp firmware/dev/core/button.py firmware/dev/core/colors.py \
   firmware/dev/core/display_model.py site/firmware/
```
Run it. Update `site/firmware/README.md`'s file list sentence.

**Step 2:** In `.github/workflows/pages.yml`, add to `on.push.paths`:

```yaml
      - 'firmware/dev/core/display_model.py'
```

**Step 3:** In `site/index.html` `bootFirmwareEngine()`, fetch and load the third module (alongside button.py/colors.py):

```js
        fetchText("firmware/display_model.py"),
...
      mp.FS.writeFile("display_model.py", displayModelSrc);
```

**Step 4:** In `PY_GLUE`:
- Delete the hand-rolled `_render()` label/color logic; replace with `from display_model import keytimes_visual, build_screen, button_visual` and have `kt_poll` return `keytimes_visual(st, cfg)` (JS reads `text`/`label_color`/`box_color`; keep returning the LED `rgb` from `resolve_keytimes_render_color` for the footswitch ring).
- Add screen functions:

```python
def screen_init(buttons_json, button_count):
    return json.dumps(build_screen(json.loads(buttons_json), button_count, 20,
                                   False, "EXP1", "EXP2"))

def screen_button(bid_index, cfg_json, on):
    return json.dumps(button_visual(json.loads(cfg_json), bool(on)))
```
(font height 20 = the shipped default `medium`.)

**Step 5:** Adjust `makeWasmKeytimes.paint()` for the new field names (`label_color` as the screen glow / `--led`, `box_color` non-black as `lit`). Run the existing headless verify (`verify2.mjs` in the session scratchpad, or re-derive: serve `site/`, drive taps/holds, assert MIDI log + labels) — behavior must be unchanged from before this task.

**Step 6: Commit**

```bash
git add tools/sync-site-firmware.sh .github/workflows/pages.yml site/index.html site/firmware/display_model.py site/firmware/README.md
git commit -m "Web demo consumes display_model: glue's hand-rolled render rules replaced by the firmware's keytimes_visual"
```

---

### Task 7: The on-page TFT screen (canvas)

**Files:**
- Modify: `site/index.html`

**Step 1: HTML.** Inside the hero `.device`, above `#frow-top`:

```html
    <canvas id="tft" width="240" height="240" aria-label="Live rendering of the device's TFT screen" hidden></canvas>
```

**Step 2: CSS.**

```css
    #tft {
      display: block;
      margin: 0 auto 1.2rem;
      width: 15rem;
      max-width: 100%;
      border: 2px solid #1c2733;
      border-radius: 0.4rem;
      background: #000;
      image-rendering: pixelated;
    }
```
`hidden` until the wasm engine boots — the JS fallback has no model to draw (screen is a wasm-only feature; do not hand-fake it, that's the drift this whole effort kills).

**Step 3: JS — canvas painter.** A `TftScreen` object owning the 2D context:

```js
  // Canvas painter for the screen model produced by display_model.py.
  // Geometry and colors come from the firmware module; this only rasterizes.
  function makeTft(canvas, model) {
    const ctx = canvas.getContext("2d");
    const hex = (n) => `#${n.toString(16).padStart(6, "0")}`;
    const buttons = model.buttons.map((b) => ({ ...b }));
    let status = model.status;
    function draw() {
      ctx.fillStyle = "#000";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      for (const b of buttons) {
        ctx.strokeStyle = hex(b.box_color);
        ctx.strokeRect(b.x + 0.5, b.y + 0.5, b.w - 1, b.h - 1);
        ctx.fillStyle = hex(b.label_color);
        ctx.font = "600 13px system-ui, sans-serif"; // stand-in for PTSans-20 PCF
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(b.text, b.cx, b.cy);
      }
      ctx.fillStyle = hex(status.color);
      ctx.fillText(status.text, status.x, status.y);
      for (const e of model.expression) {
        ctx.fillStyle = hex(e.color);
        ctx.fillText(e.text, e.x, e.y);
      }
    }
    return {
      draw,
      setButton(i, patch) { Object.assign(buttons[i], patch); draw(); },
      setStatus(text) { status = { ...status, text }; draw(); },
    };
  }
```

**Step 4: JS — wire it in `bootFirmwareEngine()`** after the engines swap:

```js
      const screenModel = JSON.parse(py.screenInit(
        JSON.stringify(PAGES[0].map((def, i) =>
          ({ label: def.label, color: def.color }))), 10));
      const tftEl = document.getElementById("tft");
      const tft = makeTft(tftEl, screenModel);
      tft.draw();
      tftEl.hidden = false;
```
Then thread updates:
- In `plainCore.toggle/tap`: after `btnPress`, `tft.setButton(i, JSON.parse(py.screenButton(JSON.stringify(cfgFor(page, i)), res.state)))` — **page 1 only** (`if (p === 0)`), since the TFT shows the active page and the model was built from page 1; also update on page flips (rebuild via `py.screenInit` with the new page's defs — mirrors `switch_page()` re-labeling).
- In `makeWasmKeytimes` `paint()` for the hero engines (VERB idx 3, TREM idx 4): `tft.setButton(idx, { text: last.text, label_color: last.label_color, box_color: last.box_color })`.
- `tft.setStatus(...)`: mirror `update_status` call sites the demo exercises — keytimes/CC sends. Cheap version: every `heroMidi` message sets status to the same string `code.py` prints (`TX CC{cc}={value}`, `PAGE {n}`). Keep the mapping in one small function with a comment pointing at `update_status` call sites.

**Step 5: Verify headless** (extend the scratchpad verify script):
- boot → canvas visible, `screenModel.buttons[0].text === "TSC"`.
- toggle TSC → canvas repaint with full green (`0x00FF00` label); sample the canvas pixel at box border via `ctx.getImageData` to assert the box color changed.
- VERB hold → screen label reads SHIM (assert via the model patch, and status shows `TX CC30=127`).
- TREM hold → page flip rebuilds screen with CLEAN/CRNCH labels.
- Fallback run (`--block-wasm`) → canvas stays `hidden`, no errors.

**Step 6: Screenshot** hero with screen visible; eyeball against the real device layout (10 boxes, two rows, status center).

**Step 7: Commit**

```bash
git add site/index.html
git commit -m "Hero gains the device's TFT screen: 240x240 canvas rendered from the firmware's own display_model in wasm"
```

---

### Task 8: Docs, plan status, wrap-up

**Files:**
- Modify: `docs/plans/2026-07-05-display-model-extraction.md` (this file — Status line)
- Modify: `docs/plans/2026-07-05-live-firmware-demo-plan.md` (add a "Follow-up" line pointing here)
- Modify: `AGENTS.md` Key Files table: add `firmware/dev/core/display_model.py` row ("Pure TFT screen model: geometry, button/keytimes visuals — shared by code.py, the web demo, and tests")

**Steps:**
1. Update Status lines.
2. Run `./tools/test-all.sh` — full suite green (verification checkpoint).
3. Commit:

```bash
git add docs/plans/ AGENTS.md
git commit -m "Docs: display_model extraction plan implemented; AGENTS.md key-files row"
```

---

## Trade-offs / notes

- **Font fidelity:** canvas uses a system font stand-in for PTSans PCF (height 20). Geometry (boxes, anchors) is exact; glyph shapes are approximate. Parsing the PCF in JS is possible later if it matters.
- **`update_status` coverage:** the demo only mirrors the status strings for events it generates. Full parity arrives with tier 3 (running `code.py` itself).
- **DUO2 seg display** is out of scope (`display_model` is TFT-only, like the `HAS_TFT` block it replaces).
- **Risk — pixel parity on device:** Task 5 is a refactor of live-performance firmware. The pytest suite plus CP-parse guard catch logic/syntax; the user's manual flash check (Task 5 Step 6) is the real gate before merging.
