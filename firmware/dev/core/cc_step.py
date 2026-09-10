"""
Pure value math for cc_inc / cc_dec buttons (issue #11).

A cc_inc/cc_dec button moves a SHARED CC value up or down instead of sending a
fixed cc_on/cc_off. The value is keyed by (channel, cc) and lives in code.py's
`cc_values` dict; this module only decides what the next value is and how a
value renders (slot index / color / text). No hardware, no I/O — unit-tested in
tests/test_cc_step.py.

Two modes, chosen by the button config:
  STEP  (cc_slots absent): value += cc_step per press, bounded by cc_min..cc_max.
  SLOT  (cc_slots present): cc_min..cc_max is split into cc_slots equal slots;
        each press moves one slot and the value sent is the MIDDLE of that
        slot, so the target device can never miss the slot's range.

Boundary rule (both modes): with cc_wrap (default) a step past cc_max lands ON
cc_min and a step below cc_min lands ON cc_max; without wrap the value clamps at
the bound and that bound is what gets sent.

CircuitPython 7.x compatible (integer math only).
"""

CC_STEP_TYPES = ("cc_inc", "cc_dec")


def is_cc_step_button(btn):
    """True for a cc_inc/cc_dec button, or a keytimes-mode button whose entries
    fire cc_inc/cc_dec (the validator copies the cc-step fields onto it)."""
    return btn.get("type") in CC_STEP_TYPES or "cc_step" in btn or "cc_slots" in btn


def cc_step_key(btn):
    """(channel, cc) key into the shared value table. Any button on any page
    with the same channel and cc moves and shows the same value."""
    return (btn.get("channel", 0), btn.get("cc", 0))


def cc_step_bounds(btn):
    """(lo, hi) value range; defaults 0..127. The validator guarantees lo < hi."""
    return btn.get("cc_min", 0), btn.get("cc_max", 127)


def cc_step_initial(btn):
    """Value the shared table starts at before any press or incoming CC."""
    lo, _ = cc_step_bounds(btn)
    return btn.get("cc_initial", lo)


def cc_step_clamp(btn, value):
    """Clamp an incoming (RX) value into the button's range."""
    lo, hi = cc_step_bounds(btn)
    return max(lo, min(hi, value))


def step_value(current, delta, lo, hi, wrap):
    """STEP mode: current + delta bounded by lo..hi. Wrap lands on the opposite
    bound (not modulo): 125 + 5 with hi=127 -> lo."""
    new = current + delta
    if new > hi:
        return lo if wrap else hi
    if new < lo:
        return hi if wrap else lo
    return new


def slot_index(value, lo, hi, slots):
    """0-based slot that `value` falls in. Values outside lo..hi clamp to the
    edge slots. Integer math: slot width is (hi - lo + 1) / slots."""
    v = max(lo, min(hi, value))
    span = hi - lo + 1
    return min(slots - 1, ((v - lo) * slots) // span)


def slot_value(index, lo, hi, slots):
    """CC value in the middle of slot `index` (0-based)."""
    span = hi - lo + 1
    return lo + ((2 * index + 1) * span) // (2 * slots)


def step_slot(current, delta, lo, hi, slots, wrap):
    """SLOT mode: move `delta` slots from the slot `current` is in and return
    the middle value of the destination slot. Wrap/clamp as step_value."""
    idx = slot_index(current, lo, hi, slots) + delta
    if idx >= slots:
        idx = 0 if wrap else slots - 1
    elif idx < 0:
        idx = slots - 1 if wrap else 0
    return slot_value(idx, lo, hi, slots)


def cc_step_next(btn, current, direction):
    """Next shared value for a press on `btn`. direction is +1 (inc) or -1 (dec)."""
    lo, hi = cc_step_bounds(btn)
    wrap = btn.get("cc_wrap", True)
    slots = btn.get("cc_slots")
    if slots:
        return step_slot(current, direction, lo, hi, slots, wrap)
    return step_value(current, direction * btn.get("cc_step", 1), lo, hi, wrap)


def cc_slot_index(btn, value):
    """0-based slot for `value` under `btn`'s slot table (SLOT mode only)."""
    lo, hi = cc_step_bounds(btn)
    return slot_index(value, lo, hi, btn.get("cc_slots", 2))


def cc_slot_color(btn, value):
    """Color name for the slot `value` is in; falls back to the button color."""
    colors = btn.get("cc_slot_colors") or []
    idx = cc_slot_index(btn, value)
    if idx < len(colors) and colors[idx]:
        return colors[idx]
    return btn.get("color", "white")


def cc_slot_name(btn, value):
    """Configured slot name for `value`, or None when the slot has no name."""
    names = btn.get("cc_slot_names") or []
    idx = cc_slot_index(btn, value)
    if idx < len(names) and names[idx]:
        return names[idx]
    return None


def cc_slot_text(btn, value):
    """Status-line text for the slot `value` is in: the slot's name, else
    '<label> n/N' (1-based) so an unnamed slot still reads as a position."""
    name = cc_slot_name(btn, value)
    if name:
        return name
    n = cc_slot_index(btn, value) + 1
    return str(btn.get("label", "")) + " " + str(n) + "/" + str(btn.get("cc_slots", 2))
