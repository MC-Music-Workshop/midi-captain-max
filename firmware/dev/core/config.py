"""
Configuration loading and validation for MIDI Captain firmware.

Handles JSON config file parsing with fallback defaults.
"""

try:
    import json
except ImportError:
    # CircuitPython has json built-in, but just in case
    json = None

VALID_TYPES = ("cc", "note", "pc", "pc_inc", "pc_dec", "hid")
VALID_MODES = ("toggle", "momentary", "flash", "select", "keytimes")
STATE_OVERRIDE_FIELDS = ("cc", "cc_on", "cc_off", "note", "velocity_on", "velocity_off", "program", "pc_step", "color", "label", "hid_action", "hid_key", "hid_modifier", "hid_delay_ms")

# Default and global-clamping bounds for long-press threshold (used by mode: "keytimes").
LONG_PRESS_THRESHOLD_DEFAULT_MS = 500
LONG_PRESS_THRESHOLD_MIN_MS = 50
LONG_PRESS_THRESHOLD_MAX_MS = 5000

# Valid colors for keytimes-mode cycle entries (button palette plus "off" for explicit LED-dark).
_CYCLE_ENTRY_COLORS = ("red", "green", "blue", "yellow", "cyan", "magenta", "orange", "purple", "white", "off")


def load_config(config_path="/config.json", button_count=10):
    """Load button configuration from JSON file.
    
    Args:
        config_path: Path to config file (default: /config.json)
        button_count: Number of buttons for fallback defaults
    
    Returns:
        Configuration dict with 'buttons' array and optional other keys
    """
    if json is None:
        return _default_config(button_count)
    
    try:
        with open(config_path, "r") as f:
            cfg = json.load(f)
            return cfg
    except Exception:
        pass
    
    return _default_config(button_count)


def _default_config(button_count):
    """Generate default configuration."""
    return {
        "buttons": [
            {"label": str(i + 1), "cc": 20 + i, "color": "white"}
            for i in range(button_count)
        ]
    }


_MIDI_BYTE_FIELDS = ("cc", "cc_on", "cc_off", "note", "velocity_on", "velocity_off", "program")

def _clamp_state_field(field, value):
    """Clamp numeric state override fields to valid MIDI ranges. Non-numeric fields pass through."""
    if field in _MIDI_BYTE_FIELDS:
        if not isinstance(value, int):
            return 0
        return max(0, min(127, value))
    if field == "pc_step":
        if not isinstance(value, int):
            return 1
        return max(1, min(127, value))
    if field == "hid_delay_ms":
        if not isinstance(value, int):
            return 50
        return max(1, min(5000, value))
    return value  # color, label, hid_action, hid_key, hid_modifier — pass through as-is


def _clamp_threshold_ms(value):
    """Clamp a long-press threshold value to schema bounds; non-int returns default."""
    if not isinstance(value, int):
        return LONG_PRESS_THRESHOLD_DEFAULT_MS
    return max(LONG_PRESS_THRESHOLD_MIN_MS, min(LONG_PRESS_THRESHOLD_MAX_MS, value))


def _clamp_midi_byte(value, default=0):
    if not isinstance(value, int):
        return default
    return max(0, min(127, value))


def _validate_keytimes_message(msg):
    """Validate a single Message object inside a keytimes-mode entry's down/up array.

    Returns a sanitized dict, or None if msg is not a valid dict.
    Discriminated by 'type'. Unknown/missing type defaults to "cc".
    """
    if not isinstance(msg, dict):
        return None
    mtype = msg.get("type")
    if mtype not in VALID_TYPES:
        mtype = "cc"
    out = {"type": mtype}
    if "channel" in msg and isinstance(msg["channel"], int) and 0 <= msg["channel"] <= 15:
        out["channel"] = msg["channel"]
    if mtype == "cc":
        out["cc"] = _clamp_midi_byte(msg.get("cc"), default=0)
        out["value"] = _clamp_midi_byte(msg.get("value"), default=127)
    elif mtype == "note":
        out["note"] = _clamp_midi_byte(msg.get("note"), default=60)
        out["velocity"] = _clamp_midi_byte(msg.get("velocity"), default=127)
    elif mtype == "pc":
        out["program"] = _clamp_midi_byte(msg.get("program"), default=0)
    elif mtype in ("pc_inc", "pc_dec"):
        step = msg.get("step", 1)
        if not isinstance(step, int):
            step = 1
        out["step"] = max(1, min(127, step))
    elif mtype == "hid":
        action = msg.get("action", "send")
        if action not in ("send", "press", "release", "delay"):
            action = "send"
        out["action"] = action
        if "key" in msg and msg["key"] is not None:
            out["key"] = str(msg["key"])
        if msg.get("modifier") in ("ctrl", "shift", "alt", "option", "windows"):
            out["modifier"] = msg["modifier"]
        delay = msg.get("delay_ms")
        if isinstance(delay, int):
            out["delay_ms"] = max(1, min(5000, delay))
    return out


def _validate_keytimes_message_list(messages):
    """Validate an array of messages (down or up slot). Returns a list (possibly empty)."""
    if not isinstance(messages, list):
        return []
    validated = []
    for msg in messages:
        v = _validate_keytimes_message(msg)
        if v is not None:
            validated.append(v)
    return validated


def _validate_keytimes_entry(entry):
    """Validate one cycle entry inside a keytimes-mode short[] or long[] array."""
    if not isinstance(entry, dict):
        return {}
    out = {}
    if "down" in entry:
        out["down"] = _validate_keytimes_message_list(entry["down"])
    if "up" in entry:
        out["up"] = _validate_keytimes_message_list(entry["up"])
    if "color" in entry:
        color = entry["color"]
        if isinstance(color, str) and color.lower() in _CYCLE_ENTRY_COLORS:
            out["color"] = color.lower()
    if entry.get("dim") is True:
        out["dim"] = True
    if "label" in entry and isinstance(entry["label"], str):
        out["label"] = entry["label"]
    return out


def _validate_keytimes_cycle(entries):
    """Validate a list of cycle entries. Returns a list (possibly empty)."""
    if not isinstance(entries, list):
        return []
    return [_validate_keytimes_entry(e) for e in entries]


def _validate_keytimes_button(btn, index, default_channel):
    """Dedicated validation path for mode: 'keytimes' buttons.

    Keytimes-mode buttons carry their message data inside per-entry down/up arrays,
    not at the top of the button — so the legacy CC/Note/PC/HID per-button fields
    do not apply here. short[] and long[] are independent cycle arrays.
    """
    label = btn.get("label", str(index + 1))
    color = btn.get("color", "white")
    off_mode = btn.get("off_mode", "dim")
    channel = btn.get("channel", default_channel)

    validated = {
        "label": label,
        "color": color,
        "mode": "keytimes",
        "off_mode": off_mode,
        "channel": channel,
        "type": "cc",  # vestigial; not used by keytimes dispatch but kept for cross-tool consistency
    }

    if "long_press_threshold_ms" in btn:
        validated["long_press_threshold_ms"] = _clamp_threshold_ms(btn.get("long_press_threshold_ms"))

    # #157: latch the long color over short (status-indicator behavior) instead of
    # the default last-press-wins. Persist only when truthy to keep configs clean.
    if btn.get("long_overlay"):
        validated["long_overlay"] = True

    short = btn.get("short")
    if short is not None:
        validated["short"] = _validate_keytimes_cycle(short)
    long_ = btn.get("long")
    if long_ is not None:
        validated["long"] = _validate_keytimes_cycle(long_)

    return validated


def validate_button(btn, index=0, global_channel=None):
    """Validate a button config dict, filling in defaults.

    Args:
        btn: Button config dict
        index: Button index (for default CC calculation)
        global_channel: Global MIDI channel (0-15), used if button doesn't specify channel

    Returns:
        Validated button config with all required fields

    Button Types:
        - "cc": Control Change (default)
        - "note": MIDI Note On/Off
        - "pc": Program Change fixed
        - "pc_inc": Program Change increment
        - "pc_dec": Program Change decrement
        - "hid": USB HID keyboard/mouse event
    """
    if global_channel is not None:
        default_channel = global_channel
    else:
        default_channel = 0

    # Keytimes: default to 1 (no cycling), clamp to 1-99
    keytimes = btn.get("keytimes", 1)
    if not isinstance(keytimes, int):
        keytimes = 1
    keytimes = max(1, min(99, keytimes))

    # Determine message type, fall back to cc if invalid.
    # For mode "keytimes" this field is ignored — message types live inside each cycle entry's
    # down/up Message objects. Keep parsing for legacy modes where button-level type still applies.
    msg_type = btn.get("type", "cc")
    if msg_type not in VALID_TYPES:
        msg_type = "cc"

    # PC types default to "flash" (brief LED pulse); CC/Note default to "toggle"
    default_mode = "flash" if msg_type in ("pc", "pc_inc", "pc_dec") else "toggle"
    raw_mode = btn.get("mode", default_mode)

    # mode: "keytimes" — short-circuit to a dedicated validation path. Other modes follow legacy.
    if raw_mode == "keytimes":
        return _validate_keytimes_button(btn, index, default_channel)

    # "select" (radio-group) is valid only on pc and cc, and only with keytimes==1.
    # Other invalid modes (and select on disallowed types) coerce back to default.
    if raw_mode == "select":
        if msg_type not in ("pc", "cc") or keytimes != 1:
            raw_mode = default_mode
        else:
            # Validate select_group: must be a non-empty string after trimming.
            raw_group = btn.get("select_group")
            if isinstance(raw_group, str):
                raw_group = raw_group.strip()
            else:
                raw_group = ""
            if not raw_group:
                raw_mode = default_mode
    elif raw_mode not in ("toggle", "momentary", "flash"):
        raw_mode = default_mode

    validated = {
        "label": btn.get("label", str(index + 1)),
        "color": btn.get("color", "white"),
        "mode": raw_mode,
        "off_mode": btn.get("off_mode", "dim"),
        "channel": btn.get("channel", default_channel),
        "type": msg_type,
        "keytimes": keytimes,
    }

    # Select-mode fields, only persisted when mode is "select".
    if raw_mode == "select":
        validated["select_group"] = btn.get("select_group", "").strip()
        raw_repress = btn.get("select_repress", "resend")
        if raw_repress not in ("resend", "nothing", "deselect"):
            raw_repress = "resend"
        validated["select_repress"] = raw_repress

    # Type-specific fields
    if msg_type == "cc":
        validated["cc"] = btn.get("cc", 20 + index)
        validated["cc_on"] = btn.get("cc_on", 127)
        validated["cc_off"] = btn.get("cc_off", 0)
    elif msg_type == "note":
        validated["note"] = btn.get("note", 60)
        validated["velocity_on"] = btn.get("velocity_on", 127)
        validated["velocity_off"] = btn.get("velocity_off", 0)
    elif msg_type == "pc":
        validated["program"] = btn.get("program", 0)
    elif msg_type in ("pc_inc", "pc_dec"):
        validated["pc_step"] = btn.get("pc_step", 1)

    # flash_ms stored for all PC types (used by firmware only when mode is flash); clamp to schema range 50-5000
    if msg_type in ("pc", "pc_inc", "pc_dec"):
        flash_ms = btn.get("flash_ms")
        if isinstance(flash_ms, int):
            validated["flash_ms"] = max(50, min(5000, flash_ms))

    # HID-specific fields
    if msg_type == "hid":
        validated["hid_action"] = btn.get("hid_action", "send")
        if validated["hid_action"] not in ("send", "press", "release", "delay"):
            validated["hid_action"] = "send"
        hid_key = btn.get("hid_key")
        if hid_key is not None:
            validated["hid_key"] = str(hid_key)
        hid_modifier = btn.get("hid_modifier")
        if hid_modifier in ("ctrl", "shift", "alt", "option", "windows"):
            validated["hid_modifier"] = hid_modifier
        hid_delay_ms = btn.get("hid_delay_ms")
        if isinstance(hid_delay_ms, int):
            validated["hid_delay_ms"] = max(1, min(5000, hid_delay_ms))

    # For keytimes > 1, validate and pass through states array
    if keytimes > 1:
        states = btn.get("states", [])
        if isinstance(states, list):
            validated_states = []
            for state in states:
                if isinstance(state, dict):
                    validated_state = {}
                    for field in STATE_OVERRIDE_FIELDS:
                        if field in state:
                            validated_state[field] = _clamp_state_field(field, state[field])
                    validated_states.append(validated_state)
            if validated_states:
                validated["states"] = validated_states

    # Deprecation warning: keytimes/states on non-keytimes-mode buttons are functional in v2.0
    # but will be removed in v3.0. Tell the user to migrate to mode: "keytimes".
    # The check happens here (after parsing) so any legacy config that actually uses these
    # fields produces a single warning per button at boot.
    if keytimes > 1 or btn.get("states"):
        _btn_label = validated.get("label", "")
        # CircuitPython 7.x doesn't support !r in f-strings — wrap values in explicit quotes.
        print(
            "[CONFIG WARN] Button " + str(index + 1) + " '" + str(_btn_label) + "' uses keytimes/states on mode='" + str(raw_mode) + "'; "
            "these fields are DEPRECATED and will be removed in v3.0. "
            "Migrate to mode='keytimes' with short[]/long[] arrays. See "
            "docs/plans/2026-05-13-issue-48-press-timings.md."
        )

    return validated


def validate_config(cfg, button_count=10):
    """Validate entire config, filling in defaults.
    
    Args:
        cfg: Raw config dict
        button_count: Expected number of buttons
        
    Returns:
        Validated config with all required fields
    """
    buttons = cfg.get("buttons", [])
    
    # Get global channel (0-15 = MIDI Ch 1-16), default to 0
    global_channel = cfg.get("global_channel", 0)
    # Clamp to valid range
    if not isinstance(global_channel, int) or global_channel < 0 or global_channel > 15:
        global_channel = 0
    
    # Extend buttons array if needed
    while len(buttons) < button_count:
        buttons.append({})
    
    # Validate each button with global channel context
    validated_buttons = [
        validate_button(btn, i, global_channel) for i, btn in enumerate(buttons[:button_count])
    ]
    
    # Top-level long-press threshold (used by keytimes-mode buttons; per-button override allowed).
    raw_threshold = cfg.get("long_press_threshold_ms", LONG_PRESS_THRESHOLD_DEFAULT_MS)
    long_press_threshold_ms = _clamp_threshold_ms(raw_threshold)

    result = {}
    for k, v in cfg.items():
        result[k] = v
    result["buttons"] = validated_buttons
    result["global_channel"] = global_channel
    result["long_press_threshold_ms"] = long_press_threshold_ms
    return result


def get_long_press_threshold_ms(cfg, btn_config):
    """Resolve the effective long-press threshold for a keytimes-mode button.

    Resolution order: per-button override > top-level config > default (500ms).
    Returns an integer in [LONG_PRESS_THRESHOLD_MIN_MS, LONG_PRESS_THRESHOLD_MAX_MS].
    """
    if "long_press_threshold_ms" in btn_config:
        return _clamp_threshold_ms(btn_config.get("long_press_threshold_ms"))
    if "long_press_threshold_ms" in cfg:
        return _clamp_threshold_ms(cfg.get("long_press_threshold_ms"))
    return LONG_PRESS_THRESHOLD_DEFAULT_MS


def get_button_state_config(btn_config, keytime_index):
    """Get button config merged with per-state overrides for a given keytime position.

    Args:
        btn_config: Validated button config dict
        keytime_index: Current keytime position (1-indexed)

    Returns:
        Dict with base values overridden by per-state values where present.
        Overridable fields: cc, cc_on, cc_off, note, velocity_on, velocity_off, program, pc_step, color, label.
    """
    # Start with base config
    result = {}
    for field in STATE_OVERRIDE_FIELDS:
        if field in btn_config:
            result[field] = btn_config[field]

    # Apply per-state overrides if keytime_index is in range
    states = btn_config.get("states", [])
    if states and 0 < keytime_index <= len(states):
        state = states[keytime_index - 1]
        for field in STATE_OVERRIDE_FIELDS:
            if field in state:
                result[field] = state[field]

    return result


def get_encoder_config(cfg):
    """Extract encoder configuration with defaults.
    
    Args:
        cfg: Full config dict
        
    Returns:
        Encoder config dict
    """
    enc = cfg.get("encoder", {})
    push = enc.get("push", {})
    global_channel = cfg.get("global_channel", 0)
    
    return {
        "enabled": enc.get("enabled", True),
        "cc": enc.get("cc", 11),
        "label": enc.get("label", "ENC"),
        "min": enc.get("min", 0),
        "max": enc.get("max", 127),
        "initial": enc.get("initial", 64),
        "steps": enc.get("steps", None),
        "channel": enc.get("channel", global_channel),
        "push": {
            "enabled": push.get("enabled", True),
            "cc": push.get("cc", 14),
            "label": push.get("label", "PUSH"),
            "mode": push.get("mode", "momentary"),
            "channel": push.get("channel", global_channel),
            "cc_on": push.get("cc_on", 127),
            "cc_off": push.get("cc_off", 0),
        },
    }


def get_expression_config(cfg):
    """Extract expression pedal configuration with defaults.

    Args:
        cfg: Full config dict

    Returns:
        Expression config dict with exp1 and exp2
    """
    exp = cfg.get("expression", {})
    exp1 = exp.get("exp1", {})
    exp2 = exp.get("exp2", {})
    global_channel = cfg.get("global_channel", 0)

    return {
        "exp1": {
            "enabled": exp1.get("enabled", True),
            "cc": exp1.get("cc", 12),
            "label": exp1.get("label", "EXP1"),
            "min": exp1.get("min", 0),
            "max": exp1.get("max", 127),
            "polarity": exp1.get("polarity", "normal"),
            "threshold": exp1.get("threshold", 2),
            "channel": exp1.get("channel", global_channel),
        },
        "exp2": {
            "enabled": exp2.get("enabled", True),
            "cc": exp2.get("cc", 13),
            "label": exp2.get("label", "EXP2"),
            "min": exp2.get("min", 0),
            "max": exp2.get("max", 127),
            "polarity": exp2.get("polarity", "normal"),
            "threshold": exp2.get("threshold", 2),
            "channel": exp2.get("channel", global_channel),
        },
    }


def get_display_config(cfg):
    """Extract display configuration with defaults.

    Args:
        cfg: Full config dict

    Returns:
        Display config dict with text size settings
    """
    display = cfg.get("display", {})

    # Validate size names
    valid_sizes = ["small", "medium", "large"]
    button_size = display.get("button_text_size", "medium")
    status_size = display.get("status_text_size", "medium")
    expression_size = display.get("expression_text_size", "medium")

    # Fallback to defaults if invalid
    if button_size not in valid_sizes:
        button_size = "medium"
    if status_size not in valid_sizes:
        status_size = "medium"
    if expression_size not in valid_sizes:
        expression_size = "medium"

    return {
        "button_text_size": button_size,
        "status_text_size": status_size,
        "expression_text_size": expression_size,
    }


def get_midi_thru_usb_to_din(cfg):
    """USB input -> 5-pin DIN output (cross-thru). Default True."""
    return bool(cfg.get("midi_thru_usb_to_din", True))


def get_midi_thru_din_to_usb(cfg):
    """5-pin DIN input -> USB output (cross-thru). Default True."""
    return bool(cfg.get("midi_thru_din_to_usb", True))


def get_midi_thru_din_to_din(cfg):
    """5-pin DIN input -> 5-pin DIN output (classic MIDI THRU pass-through
    for daisy-chaining controllers downstream). Default True (matches OEM)."""
    return bool(cfg.get("midi_thru_din_to_din", True))


def get_midi_thru_usb_to_usb(cfg):
    """USB input -> USB output (loopback to host). Default False — echoing
    back to the host can cause duplicate notes or feedback when the DAW also
    has MIDI echo enabled. Opt-in for niche routing setups."""
    return bool(cfg.get("midi_thru_usb_to_usb", False))


def get_dev_mode(cfg):
    """Extract development mode setting from config.

    In development mode the USB drive mounts on every boot without needing
    to hold Switch 1.  In performance mode (the default) the drive is hidden
    unless Switch 1 is held during boot.

    Args:
        cfg: Full config dict

    Returns:
        True if development mode is enabled, False otherwise
    """
    return bool(cfg.get("dev_mode", False))


def validate_usb_drive_name(name):
    """Validate USB drive name for FAT32 compatibility.
    
    FAT32 volume labels have strict requirements:
    - Maximum 11 characters
    - Uppercase alphanumeric + underscore only
    - No spaces or special characters
    
    Args:
        name: Proposed drive name string
        
    Returns:
        Valid drive name (sanitized) or "MIDICAPTAIN" if invalid
    """
    if not name or not isinstance(name, str):
        return "MIDICAPTAIN"
    
    # Convert to uppercase and strip whitespace
    name = name.upper().strip()
    
    # Filter to valid characters (alphanumeric + underscore).
    # Avoid str.isalnum() — not available in CircuitPython 7.x.
    # name is already uppercased, so only A-Z, 0-9, and _ are valid.
    name = "".join(c for c in name if ('A' <= c <= 'Z') or ('0' <= c <= '9') or c == '_')
    
    # Truncate to 11 characters
    if len(name) > 11:
        name = name[:11]
    
    # Must have at least 1 character
    if len(name) == 0:
        return "MIDICAPTAIN"
    
    return name


def get_usb_drive_name(cfg):
    """Extract and validate USB drive name from config.
    
    Args:
        cfg: Full config dict
        
    Returns:
        Validated USB drive name string
    """
    name = cfg.get("usb_drive_name", "MIDICAPTAIN")
    return validate_usb_drive_name(name)
