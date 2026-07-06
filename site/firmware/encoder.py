"""
Rotary encoder value tracking — pure logic shared by firmware and the web demo.

No hardware: the caller supplies rotation deltas (from rotaryio on-device, or
pointer drags in the browser) via turn(). Mirrors the value/slot/emit rules
that were inline in code.py handle_encoder(). Same zero-drift pattern as
core/button.py and core/display_model.py.

CircuitPython 7.x compatible (guarded by tools/check-circuitpython-parse.sh).
"""


class EncoderState:
    """Tracks an encoder's 0-127 value (and optional stepped slot).

    turn(delta) applies a rotation and returns the CC Message dict to send, or
    None when nothing should fire (stepped mode with the slot unchanged).
    """

    def __init__(self, cc, initial=64, steps=None):
        self.cc = cc
        # steps only meaningful when >1; normalize anything else to None (normal mode).
        self.steps = steps if (steps and steps > 1) else None
        self.value = max(0, min(127, initial))
        self.slot = None
        if self.steps:
            self.slot = min(self.value // (128 // self.steps), self.steps - 1)

    def turn(self, delta):
        """Apply a rotation delta (in detents). Returns {"type","cc","value"} or None.

        Normal mode: emits the clamped 0-127 value on every detent (matching the
        firmware, which sends on each physical position change even at a clamp
        boundary). Stepped mode: emits the slot index only when the slot changes.
        """
        self.value = max(0, min(127, self.value + delta))
        if self.steps:
            slot_size = 128 // self.steps
            new_slot = min(self.value // slot_size, self.steps - 1)
            if new_slot != self.slot:
                self.slot = new_slot
                return {"type": "cc", "cc": self.cc, "value": self.slot}
            return None
        return {"type": "cc", "cc": self.cc, "value": self.value}
