"""
Button and switch handling for MIDI Captain firmware.

Provides Switch class for input handling and ButtonState for state tracking.
"""


class Switch:
    """Footswitch with state tracking and edge detection.
    
    Expects a CircuitPython digitalio.DigitalInOut object or compatible mock.
    Uses pull-up configuration (True = not pressed, False = pressed).
    """

    def __init__(self, pin, digitalio_module=None):
        """Initialize switch on given pin.
        
        Args:
            pin: Board pin object
            digitalio_module: Optional digitalio module (for dependency injection in tests)
        """
        if digitalio_module is None:
            import digitalio as digitalio_module
        
        self.io = digitalio_module.DigitalInOut(pin)
        self.io.direction = digitalio_module.Direction.INPUT
        self.io.pull = digitalio_module.Pull.UP
        self.last_state = True  # Pull-up: True = not pressed

    @property
    def pressed(self):
        """Return True if switch is currently pressed."""
        return not self.io.value

    def changed(self):
        """Check if switch state changed since last call.
        
        Returns:
            Tuple of (changed: bool, pressed: bool)
        """
        current = self.pressed
        changed = current != self.last_state
        self.last_state = current
        return changed, current


class ButtonState:
    """Tracks toggle state and mode for a button.
    
    Supports toggle, momentary, and flash modes with bidirectional sync.
    Also supports keytimes (multi-press cycling through states).
    """
    
    def __init__(self, cc, mode="toggle", initial_state=False, keytimes=1):
        """Initialize button state.
        
        Args:
            cc: MIDI CC number for this button
            mode: "toggle", "momentary", or "flash" (flash dispatch handled by caller)
            initial_state: Initial on/off state
            keytimes: Number of states to cycle through (1-99), default 1 (no cycling)
        """
        self.cc = cc
        self.mode = mode
        self._state = initial_state
        self.keytimes = max(1, min(99, keytimes))  # Clamp to 1-99
        self.current_keytime = 1  # Current position in keytime cycle (1-indexed)
    
    @property
    def state(self):
        """Current on/off state."""
        return self._state
    
    @state.setter
    def state(self, value):
        """Set state (used by host override)."""
        self._state = bool(value)
    
    def advance_keytime(self):
        """Advance to next keytime state, cycling back to 1 after max.

        No-op when keytimes == 1.
        """
        if self.keytimes > 1:
            self.current_keytime = (self.current_keytime % self.keytimes) + 1

    def on_press(self):
        """Handle button press.

        For keytimes > 1: advances to next keytime state via advance_keytime().

        NOTE: handle_switches() in code.py does NOT call this method — it calls
        advance_keytime() directly to keep keytime management and MIDI dispatch
        in one place. This method is used by tests and any external consumers
        that need the full ButtonState API without MIDI dispatch.

        Returns:
            Tuple of (state_changed: bool, new_state: bool, midi_value: int)
        """
        if self.mode == "momentary":
            self._state = True
            self.advance_keytime()
            return True, True, 127
        else:  # toggle
            if self.keytimes > 1:
                self.advance_keytime()
                self._state = True  # Always "on" when cycling keytimes
                return True, True, 127
            else:
                # Standard toggle behavior
                self._state = not self._state
                return True, self._state, 127 if self._state else 0
    
    def on_release(self):
        """Handle button release.

        NOTE: handle_switches() in code.py does NOT call this method — release
        handling is inlined there alongside MIDI dispatch. This method is used
        by tests and any external consumers that need the full ButtonState API.

        Returns:
            Tuple of (state_changed: bool, new_state: bool, midi_value: int)
            For toggle mode, returns (False, state, None) - no action on release
        """
        if self.mode == "momentary":
            self._state = False
            return True, False, 0
        else:  # toggle
            return False, self._state, None
    
    def on_midi_receive(self, value):
        """Handle incoming MIDI CC value (host override).
        
        Args:
            value: MIDI CC value (0-127)
            
        Returns:
            New state (True if value > 63)
        """
        self._state = value > 63
        return self._state
    
    def get_keytime(self):
        """Get current keytime index (1-indexed).
        
        Returns:
            Current keytime position (1 to keytimes)
        """
        return self.current_keytime
    
    def reset_keytime(self):
        """Reset keytime cycle back to position 1."""
        self.current_keytime = 1
        self._state = False


class PressTracker:
    """Classifies button press events into short/long timing slots.

    Consumes (pressed, now) on every poll and returns a list of timing events
    that fired during the transition. Designed to compose with Switch — the
    caller passes Switch.pressed and time.monotonic() each loop.

    Threshold defines the boundary between short and long presses. A release
    before threshold emits short_up; a release after emits long_up. The
    short_down event fires immediately on every physical press; long_down
    fires once when the threshold is reached while still held.

    Used only by buttons in mode: "keytimes" (see #48 / docs/plans/2026-05-13-...).
    """

    def __init__(self, threshold_ms):
        self.threshold_s = threshold_ms / 1000.0
        self._pressed = False
        self._down_at = None
        self._long_fired = False

    def update(self, pressed, now):
        """Process one poll. Returns a list of event names that fired.

        Event names: "short_down", "short_up", "long_down", "long_up".
        Multiple events can fire in one update (e.g. long_down arriving during
        a steady hold). Returned list preserves firing order.
        """
        events = []

        if pressed and not self._pressed:
            self._pressed = True
            self._down_at = now
            self._long_fired = False
            events.append("short_down")
        elif pressed and self._pressed:
            if not self._long_fired and (now - self._down_at) >= self.threshold_s:
                self._long_fired = True
                events.append("long_down")
        elif not pressed and self._pressed:
            self._pressed = False
            if self._long_fired:
                events.append("long_up")
            else:
                events.append("short_up")
            self._down_at = None
            self._long_fired = False

        return events


class PressCycle:
    """Tracks the current entry index for one timing class (short or long).

    Independent of PressTracker — a button has two PressCycles (short, long)
    each managing its own index. Advanced once per physical press in which
    at least one event from this class fired.

    Used only by buttons in mode: "keytimes".
    """

    def __init__(self, length):
        self.length = length
        self.index = 0

    def advance(self):
        """Advance index by 1, wrapping at length. No-op when length <= 0."""
        if self.length > 0:
            self.index = (self.index + 1) % self.length

    def reset(self):
        """Reset index to 0 (e.g. on power cycle or config reload)."""
        self.index = 0


class KeytimesButtonState:
    """All per-button runtime state for a mode: "keytimes" button.

    Aggregates PressTracker (timing classifier), two PressCycles (one per timing
    class), and the inherited color/label/dim state for each layer. The dispatcher
    reads from a button's config to fire messages and updates this state's
    cycle indices and inherited colors after each press.
    """

    def __init__(self, threshold_ms, short_length, long_length):
        self.tracker = PressTracker(threshold_ms)
        self.short_cycle = PressCycle(short_length)
        self.long_cycle = PressCycle(long_length)
        # Inherited render state — updated when an entry sets a color/label/dim.
        # color is None until the first event with a color fires; rendering falls
        # through to button-level color or LED-off depending on the layer.
        self.short_color = None
        self.long_color = None
        self.short_dim = False
        self.long_dim = False
        self.short_label = None
        self.long_label = None
        # Per-press "did any event from this cycle fire" flags. Cycles advance
        # at press-end (short_up or long_up) if their flag is set.
        self._fired_short = False
        self._fired_long = False


# Map from event names emitted by PressTracker to (cycle_name, slot_name).
_KEYTIMES_EVENT_MAP = {
    "short_down": ("short", "down"),
    "short_up":   ("short", "up"),
    "long_down":  ("long",  "down"),
    "long_up":    ("long",  "up"),
}


def dispatch_keytimes_events(events, state, btn_config, message_callback):
    """Dispatch a sequence of timing events through a keytimes-mode button's config.

    Pure logic — no hardware, no time, no I/O. Tests inject a callback to capture
    dispatched messages and assert behavior; the live firmware passes a real
    MIDI/HID dispatch function.

    Args:
        events: list of event names from PressTracker.update()
        state: KeytimesButtonState for this button
        btn_config: validated button config dict (must have mode == "keytimes")
        message_callback: fn(message_dict) called for each Message to dispatch

    Side effects:
        - Calls message_callback for each Message in the entries' down/up arrays
        - Updates state.{short,long}_color/dim/label from entries that set them
        - Sets state._fired_short / _fired_long
        - Advances state.short_cycle / long_cycle on press-end events (short_up/long_up)
    """
    short_entries = btn_config.get("short", []) or []
    long_entries = btn_config.get("long", []) or []

    for event in events:
        cycle_name, slot = _KEYTIMES_EVENT_MAP.get(event, (None, None))
        if cycle_name is None:
            continue

        if cycle_name == "short":
            entries = short_entries
            cycle = state.short_cycle
            state._fired_short = True
        else:
            entries = long_entries
            cycle = state.long_cycle
            state._fired_long = True

        if entries:
            idx = cycle.index
            if 0 <= idx < len(entries):
                entry = entries[idx]
                for msg in entry.get(slot, []) or []:
                    message_callback(msg)
                # Update inherited render state from this entry. color inherits across
                # entries (only updates if entry has one); dim and label are per-entry
                # but treated symmetrically here — only updated if the field is present.
                if "color" in entry:
                    if cycle_name == "short":
                        state.short_color = entry["color"]
                    else:
                        state.long_color = entry["color"]
                if "dim" in entry:
                    if cycle_name == "short":
                        state.short_dim = bool(entry["dim"])
                    else:
                        state.long_dim = bool(entry["dim"])
                else:
                    # Entry without explicit dim resets dim to False (non-inheriting).
                    if cycle_name == "short":
                        state.short_dim = False
                    else:
                        state.long_dim = False
                if "label" in entry:
                    if cycle_name == "short":
                        state.short_label = entry["label"]
                    else:
                        state.long_label = entry["label"]

        # On press-end, advance cycles whose events fired during this press, then reset flags.
        if event in ("short_up", "long_up"):
            if state._fired_short:
                state.short_cycle.advance()
            if state._fired_long:
                state.long_cycle.advance()
            state._fired_short = False
            state._fired_long = False
