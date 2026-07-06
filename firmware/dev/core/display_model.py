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
