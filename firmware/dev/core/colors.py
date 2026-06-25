"""
Color utilities for MIDI Captain firmware.

Provides color palette and conversion functions for LEDs and display.
"""

# Named color palette (RGB tuples)
COLORS = {
    "red": (255, 0, 0),
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
    "yellow": (255, 255, 0),
    "cyan": (0, 255, 255),
    "magenta": (255, 0, 255),
    "orange": (255, 128, 0),
    "purple": (128, 0, 255),
    "white": (255, 255, 255),
    "off": (0, 0, 0),
}


def get_color(name):
    """Get RGB tuple from color name, with fallback to white.
    
    Args:
        name: Color name (case-insensitive)
        
    Returns:
        RGB tuple (r, g, b) with values 0-255
    """
    return COLORS.get(name.lower(), COLORS["white"])


def dim_color(rgb, factor=0.15):
    """Return a dimmed version of an RGB color.
    
    Args:
        rgb: RGB tuple (r, g, b)
        factor: Brightness factor (0.0-1.0), default 0.15
        
    Returns:
        Dimmed RGB tuple
    """
    return tuple(int(c * factor) for c in rgb)


def rgb_to_hex(rgb):
    """Convert RGB tuple to hex integer for display.
    
    Args:
        rgb: RGB tuple (r, g, b)
        
    Returns:
        Integer in 0xRRGGBB format
    """
    return (rgb[0] << 16) | (rgb[1] << 8) | rgb[2]


def get_off_color(color_rgb, off_mode="dim"):
    """Get the color to use when button is off.

    Args:
        color_rgb: The button's on-state RGB color
        off_mode: "dim" for dimmed color, "off" for completely off

    Returns:
        RGB tuple for the off state
    """
    if off_mode == "off":
        return (0, 0, 0)
    return dim_color(color_rgb)


def get_off_color_for_display(color_rgb, off_mode="dim"):
    """Get the color to use for display labels when button is off.

    Labels should always be visible regardless of off_mode setting.

    Args:
        color_rgb: The button's on-state RGB color
        off_mode: Ignored - labels always show dim for visibility

    Returns:
        RGB tuple for the off state (always dimmed for visibility)
    """
    # Always return dim color to keep labels visible on display
    return dim_color(color_rgb)


def compute_keytimes_led_color(short_color, short_dim, long_color, long_dim, button_color=None):
    """Resolve the LED color for a mode: "keytimes" button per the two-layer render rule.

    Render rule (from docs/plans/2026-05-13-issue-48-press-timings.md):
      - short.color == "off"         -> LED off (short is a kill switch)
      - long.color set (not "off")   -> LED = long.color (decoration over primary)
      - short.color set              -> LED = short.color
      - button_color set             -> LED = button_color (fallback when all entries inherit)
      - else                         -> LED off

    The 'dim' flag on whichever layer wins applies via dim_color() (15% brightness).
    For the button-level fallback, dim applies if either layer's dim flag is set —
    the user can dim an inherit-color entry without specifying a color.

    NOTE: the short>long precedence below resolves whatever layers the CALLER
    passes. _render_keytimes_led() suppresses the inactive layer (passes its color
    as None) so the last-fired timing class owns the render — see its docstring.
    Passing both layers populated keeps the original "long decorates over short"
    composition, which the unit tests exercise directly.

    Args:
        short_color: color name from short cycle layer, or None if unset
        short_dim: True to render short layer at reduced brightness
        long_color: color name from long cycle layer, or None if unset
        long_dim: True to render long layer at reduced brightness
        button_color: button-level color name (required schema field) used as
            fallback when no cycle entry has set a color. Pass None to render
            OFF in that case.

    Returns:
        RGB tuple (r, g, b) with values 0-255
    """
    if short_color == "off":
        return COLORS["off"]
    if long_color and long_color != "off":
        rgb = get_color(long_color)
        if long_dim:
            rgb = dim_color(rgb)
        return rgb
    if short_color:
        rgb = get_color(short_color)
        if short_dim:
            rgb = dim_color(rgb)
        return rgb
    if button_color:
        rgb = get_color(button_color)
        # Either layer's dim applies — the user marked the current entry as dim
        # even though they left its color as "(inherit)".
        if short_dim or long_dim:
            rgb = dim_color(rgb)
        return rgb
    return COLORS["off"]


def resolve_keytimes_render_color(last_fired, short_color, short_dim,
                                  long_color, long_dim, button_color=None,
                                  long_overlay=False):
    """Resolve a keytimes button's render color gated by the last-fired timing class.

    #157 ("sticky long color"): by default the LED reflects only the most recently
    fired timing class, mirroring the last_fired label rule introduced in #143.
    Without this gate, a long press leaves state.long_color set indefinitely and
    compute_keytimes_led_color()'s long>short precedence keeps the LED stuck on the
    long color across every subsequent short press — the label flips back but the
    color does not.

    long_overlay=True opts back into the latching-modifier behavior: the long layer
    decorates short persistently (full two-layer composition), so a long color stays
    lit across subsequent short presses. Useful as a status indicator (e.g. a
    shimmer-on light riding over a reverb short cycle).

    With overlay off, this suppresses the inactive layer (passing its color as None,
    dim as False) so the active class owns the render, then defers to
    compute_keytimes_led_color() for the kill-switch / precedence / dim /
    button-fallback rules. last_fired == None (before the first press) passes both
    layers unsuppressed, falling through to the button-level color.

    Args:
        last_fired: "short", "long", or None — the timing class that owns the render
        short_color, short_dim, long_color, long_dim, button_color: see
            compute_keytimes_led_color()
        long_overlay: True to keep long decorating short persistently (no last_fired
            gating); default False gives last-press-wins.

    Returns:
        RGB tuple (r, g, b) with values 0-255
    """
    if not long_overlay:
        if last_fired == "short":
            long_color, long_dim = None, False
        elif last_fired == "long":
            short_color, short_dim = None, False
    return compute_keytimes_led_color(short_color, short_dim,
                                      long_color, long_dim, button_color)
