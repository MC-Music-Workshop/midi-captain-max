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
STATE_OVERRIDE_FIELDS = ("cc", "cc_on", "cc_off", "note", "velocity_on", "velocity_off", "program", "pc_step", "color", "label", "hid_action", "hid_key", "hid_modifier", "hid_delay_ms")


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

    # Determine message type, fall back to cc if invalid
    msg_type = btn.get("type", "cc")
    if msg_type not in VALID_TYPES:
        msg_type = "cc"

    # PC types default to "flash" (brief LED pulse); CC/Note default to "toggle"
    default_mode = "flash" if msg_type in ("pc", "pc_inc", "pc_dec") else "toggle"
    raw_mode = btn.get("mode", default_mode)
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
    
    result = {}
    for k, v in cfg.items():
        result[k] = v
    result["buttons"] = validated_buttons
    result["global_channel"] = global_channel
    return result


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
