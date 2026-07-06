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

    # With long_overlay, an active long layer (its color set, not a kill) is a
    # persistent mode — the label rides with the color, so a short tap doesn't
    # flip the mode name back. Clearing the long layer (mode off) falls through
    # to the normal last_fired gating.
    overlay_mode_on = long_overlay and state.long_color and state.long_color != "off"
    if overlay_mode_on or state.last_fired == "long":
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
