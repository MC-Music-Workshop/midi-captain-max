"""
Per-LED colors and animations for a switch's three NeoPixels.

A "style" is a validated LedStyle dict (see config.schema.json and
core/config.py::validate_led_style): optional `pixels` (three color names),
`animation` ("solid" | "flash" | "spin") and `speed_ms`.

Pure logic, no hardware: code.py turns a style into a pattern and frames once
per state change, then update_led_animations() only picks the current frame.
"""

from core.colors import (
    COLORS,
    compute_keytimes_led_color,
    dim_color,
    get_color,
    get_off_color,
)

ANIMATIONS = ("solid", "flash", "spin")
SPEED_MS_DEFAULT = 250
SPEED_MS_MIN = 50
SPEED_MS_MAX = 5000
PIXELS_PER_SWITCH = 3

_OFF = COLORS["off"]


def _pixels_rgb(names, dim=False):
    """Three color names -> tuple of three RGB tuples ("off" is black)."""
    out = []
    for name in names:
        rgb = _OFF if name == "off" else get_color(name)
        if dim:
            rgb = dim_color(rgb)
        out.append(rgb)
    return tuple(out)


def _animation(style):
    if style:
        return style.get("animation", "solid"), style.get("speed_ms", SPEED_MS_DEFAULT)
    return "solid", SPEED_MS_DEFAULT


def style_frames(pattern, animation):
    """Frames for one switch: a tuple of patterns (each three RGB tuples).

    solid -> one frame (no animation work in the main loop)
    flash -> pattern, then all-off
    spin  -> the pattern rotated one position per frame. A uniform pattern
             would look solid when rotated, so it spins as one lit LED.
    A dark pattern never animates: there's nothing to see.
    """
    pattern = tuple(pattern)
    if animation not in ("flash", "spin") or pattern == (_OFF, _OFF, _OFF):
        return (pattern,)
    if animation == "flash":
        return (pattern, (_OFF, _OFF, _OFF))
    if pattern[0] == pattern[1] == pattern[2]:
        pattern = (pattern[0], _OFF, _OFF)
    return (
        pattern,
        (pattern[2], pattern[0], pattern[1]),
        (pattern[1], pattern[2], pattern[0]),
    )


def frame_index(start, now, speed_ms, frame_count):
    """Which frame is showing `now` for an animation that started at `start`."""
    if frame_count <= 1 or speed_ms <= 0:
        return 0
    return int((now - start) * 1000 / speed_ms) % frame_count


def resolve_button_led(btn_config, on, color_rgb):
    """LED pattern + animation for a toggle/momentary/flash/select button.

    Args:
        btn_config: validated button config
        on: button state
        color_rgb: the button's resolved on color (keytime state already applied)

    Returns:
        (pattern, animation, speed_ms): pattern is three RGB tuples.
    """
    led_on = btn_config.get("led_on")
    if on:
        if led_on and "pixels" in led_on:
            pattern = _pixels_rgb(led_on["pixels"])
        else:
            pattern = (color_rgb, color_rgb, color_rgb)
        animation, speed = _animation(led_on)
        return pattern, animation, speed

    led_off = btn_config.get("led_off")
    off_color = btn_config.get("off_color")
    if led_off and "pixels" in led_off:
        pattern = _pixels_rgb(led_off["pixels"])
    elif off_color:
        rgb = get_color(off_color)
        pattern = (rgb, rgb, rgb)
    elif btn_config.get("off_mode", "dim") == "off":
        pattern = (_OFF, _OFF, _OFF)
    elif led_on and "pixels" in led_on:
        # The off look follows the on look: dimmed multi-color, not dimmed `color`.
        pattern = _pixels_rgb(led_on["pixels"], dim=True)
    else:
        rgb = get_off_color(color_rgb, "dim")
        pattern = (rgb, rgb, rgb)
    animation, speed = _animation(led_off)
    return pattern, animation, speed


def _has_pixels(style):
    return bool(style) and "pixels" in style


def resolve_keytimes_led(last_fired, short_color, short_dim, short_led,
                         long_color, long_dim, long_led,
                         button_color=None, long_overlay=False):
    """LED pattern + animation for a mode: "keytimes" button.

    Same layer rules as colors.resolve_keytimes_render_color() (last-fired
    gating unless long_overlay, short "off" kill switch, long over short,
    button-color fallback), with one addition: an entry whose `led` has pixels
    counts as setting a color, so it can win its layer without a `color`.

    Returns:
        (pattern, animation, speed_ms)
    """
    if not long_overlay:
        if last_fired == "short":
            long_color, long_dim, long_led = None, False, None
        elif last_fired == "long":
            short_color, short_dim, short_led = None, False, None

    if short_color == "off":
        return (_OFF, _OFF, _OFF), "solid", SPEED_MS_DEFAULT

    if (long_color and long_color != "off") or _has_pixels(long_led):
        style, dim = long_led, long_dim
    elif short_color or _has_pixels(short_led):
        style, dim = short_led, short_dim
    else:
        # Button-color fallback: whichever layer is live may still animate it.
        style, dim = long_led or short_led, False

    if _has_pixels(style):
        pattern = _pixels_rgb(style["pixels"], dim)
    else:
        rgb = compute_keytimes_led_color(short_color, short_dim,
                                         long_color, long_dim, button_color)
        pattern = (rgb, rgb, rgb)
    animation, speed = _animation(style)
    return pattern, animation, speed
