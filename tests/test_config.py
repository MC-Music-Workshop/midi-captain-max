"""
Tests for configuration loading and validation.

Tests the actual core/config.py module.
"""

import pytest
import json
import sys
from pathlib import Path

# Add firmware/dev to path
FIRMWARE_DIR = Path(__file__).parent.parent / "firmware" / "dev"
sys.path.insert(0, str(FIRMWARE_DIR))

from core.config import (
    load_config,
    validate_button,
    validate_config,
    get_encoder_config,
    get_expression_config,
    get_button_state_config,
)


class TestConfigValidation:
    """Test config parsing and validation logic."""
    
    def test_sample_config_has_buttons(self, sample_config):
        """Config must have a buttons array."""
        assert "buttons" in sample_config
        assert isinstance(sample_config["buttons"], list)
    
    def test_button_has_required_fields(self, sample_config):
        """Each button must have label and color (cc is only required for CC-type buttons)."""
        for btn in sample_config["buttons"]:
            assert "label" in btn
            assert "color" in btn
    
    def test_cc_numbers_in_valid_range(self, sample_config):
        """CC numbers must be 0-127."""
        for btn in sample_config["buttons"]:
            assert 0 <= btn["cc"] <= 127
    
    def test_colors_are_valid(self, sample_config):
        """Colors must be known color names."""
        valid_colors = {"red", "green", "blue", "yellow", "cyan", 
                       "magenta", "orange", "purple", "white", "off"}
        for btn in sample_config["buttons"]:
            assert btn["color"].lower() in valid_colors


class TestConfigParsing:
    """Test JSON config file parsing."""
    
    def test_parse_valid_json(self, tmp_path):
        """Can parse a valid config file."""
        config_file = tmp_path / "config.json"
        config_data = {
            "buttons": [
                {"label": "Test", "cc": 50, "color": "red"}
            ]
        }
        config_file.write_text(json.dumps(config_data))
        
        with open(config_file) as f:
            loaded = json.load(f)
        
        assert loaded["buttons"][0]["label"] == "Test"
        assert loaded["buttons"][0]["cc"] == 50
    
    def test_empty_buttons_array(self, tmp_path):
        """Empty buttons array is valid (uses defaults)."""
        config_file = tmp_path / "config.json"
        config_file.write_text('{"buttons": []}')
        
        with open(config_file) as f:
            loaded = json.load(f)
        
        assert loaded["buttons"] == []
    
    def test_extra_fields_ignored(self, tmp_path):
        """Unknown fields in config are silently ignored."""
        config_file = tmp_path / "config.json"
        config_data = {
            "buttons": [{"label": "1", "cc": 20, "color": "red"}],
            "unknown_field": "ignored",
            "future_feature": True
        }
        config_file.write_text(json.dumps(config_data))
        
        with open(config_file) as f:
            loaded = json.load(f)
        
        # Should load without error
        assert "buttons" in loaded


class TestButtonModes:
    """Test button mode configuration."""
    
    def test_default_mode_is_toggle(self):
        """Buttons default to toggle mode if not specified."""
        button = {"label": "Test", "cc": 50, "color": "red"}
        mode = button.get("mode", "toggle")
        assert mode == "toggle"
    
    def test_momentary_mode(self):
        """Can specify momentary mode."""
        button = {"label": "Test", "cc": 50, "color": "red", "mode": "momentary"}
        assert button["mode"] == "momentary"
    
    def test_toggle_mode_explicit(self):
        """Can explicitly specify toggle mode."""
        button = {"label": "Test", "cc": 50, "color": "red", "mode": "toggle"}
        assert button["mode"] == "toggle"


class TestValidateButton:
    """Test validate_button function from core/config.py."""
    
    def test_fills_missing_fields(self):
        """Fills in defaults for missing fields."""
        btn = validate_button({}, index=0)
        
        assert btn["label"] == "1"
        assert btn["cc"] == 20
        assert btn["color"] == "white"
        assert btn["mode"] == "toggle"
        assert btn["off_mode"] == "dim"
        assert btn["channel"] == 0  # Default MIDI channel 1
        assert btn["cc_on"] == 127
        assert btn["cc_off"] == 0
    
    def test_preserves_existing_fields(self):
        """Keeps existing values."""
        btn = validate_button({"label": "MUTE", "cc": 99, "color": "red"}, index=5)
        
        assert btn["label"] == "MUTE"
        assert btn["cc"] == 99
        assert btn["color"] == "red"
    
    def test_index_affects_defaults(self):
        """Index is used for default label and CC."""
        btn = validate_button({}, index=7)
        
        assert btn["label"] == "8"  # 1-indexed
        assert btn["cc"] == 27  # 20 + 7
    
    def test_global_channel_inheritance(self):
        """Button uses global channel when not specified."""
        btn = validate_button({}, index=0, global_channel=5)
        assert btn["channel"] == 5
    
    def test_button_channel_override(self):
        """Button can override global channel."""
        btn = validate_button({"channel": 10}, index=0, global_channel=5)
        assert btn["channel"] == 10
    
    def test_custom_cc_values(self):
        """Button can specify custom cc_on and cc_off values."""
        btn = validate_button({"cc_on": 100, "cc_off": 20}, index=0)
        assert btn["cc_on"] == 100
        assert btn["cc_off"] == 20
    
    def test_keytimes_default(self):
        """Button defaults to keytimes=1 when not specified."""
        btn = validate_button({}, index=0)
        assert btn["keytimes"] == 1
    
    def test_keytimes_explicit_value(self):
        """Button can specify keytimes value."""
        btn = validate_button({"keytimes": 3}, index=0)
        assert btn["keytimes"] == 3
    
    def test_keytimes_clamped_to_valid_range(self):
        """Keytimes is clamped to 1-99."""
        btn_low = validate_button({"keytimes": 0}, index=0)
        assert btn_low["keytimes"] == 1
        
        btn_high = validate_button({"keytimes": 150}, index=0)
        assert btn_high["keytimes"] == 99
        
        btn_valid = validate_button({"keytimes": 5}, index=0)
        assert btn_valid["keytimes"] == 5
    
    def test_keytimes_invalid_type_defaults_to_one(self):
        """Non-integer keytimes defaults to 1."""
        btn = validate_button({"keytimes": "invalid"}, index=0)
        assert btn["keytimes"] == 1
    
    def test_keytimes_with_states(self):
        """Button with keytimes > 1 can have states array."""
        btn = validate_button({
            "keytimes": 3,
            "states": [
                {"cc_on": 64, "color": "red"},
                {"cc_on": 96, "color": "blue"},
                {"cc_on": 127, "color": "green"}
            ]
        }, index=0)
        assert btn["keytimes"] == 3
        assert "states" in btn
        assert len(btn["states"]) == 3

    def test_validate_button_clamps_invalid_cc_in_states(self):
        """Out-of-range numeric state overrides are clamped, not passed through raw."""
        btn = validate_button({
            "type": "cc",
            "cc": 20,
            "keytimes": 2,
            "states": [{"cc": 200, "cc_on": -10, "cc_off": 999}]
        }, index=0)
        assert btn["states"][0]["cc"] == 127      # clamped to max
        assert btn["states"][0]["cc_on"] == 0     # clamped to min
        assert btn["states"][0]["cc_off"] == 127  # clamped to max

    def test_validate_button_clamps_invalid_note_in_states(self):
        btn = validate_button({
            "type": "note",
            "note": 60,
            "keytimes": 2,
            "states": [{"note": 200, "velocity_on": -5}]
        }, index=0)
        assert btn["states"][0]["note"] == 127
        assert btn["states"][0]["velocity_on"] == 0

    def test_validate_button_preserves_program_in_states(self):
        btn = validate_button({
            "type": "pc",
            "program": 5,
            "keytimes": 2,
            "states": [{"program": 10}, {"program": 20}]
        }, index=0)
        assert btn["states"][0]["program"] == 10
        assert btn["states"][1]["program"] == 20

    def test_validate_button_preserves_pc_step_in_states(self):
        btn = validate_button({
            "type": "pc_inc",
            "pc_step": 1,
            "keytimes": 2,
            "states": [{"pc_step": 5}, {"pc_step": 10}]
        }, index=0)
        assert btn["states"][0]["pc_step"] == 5
        assert btn["states"][1]["pc_step"] == 10


class TestButtonMessageTypes:
    """Tests for multi-type button message support."""

    def test_default_type_is_cc(self):
        btn = validate_button({}, index=0)
        assert btn["type"] == "cc"

    def test_cc_type_explicit(self):
        btn = validate_button({"type": "cc", "cc": 50}, index=0)
        assert btn["type"] == "cc"
        assert btn["cc"] == 50
        assert btn["cc_on"] == 127
        assert btn["cc_off"] == 0

    def test_cc_type_no_note_fields(self):
        btn = validate_button({"type": "cc"}, index=0)
        assert "note" not in btn
        assert "velocity_on" not in btn
        assert "velocity_off" not in btn

    def test_cc_type_no_pc_fields(self):
        btn = validate_button({"type": "cc"}, index=0)
        assert "program" not in btn
        assert "pc_step" not in btn

    def test_note_type(self):
        btn = validate_button({"type": "note", "note": 60}, index=0)
        assert btn["type"] == "note"
        assert btn["note"] == 60
        assert btn["velocity_on"] == 127
        assert btn["velocity_off"] == 0

    def test_note_type_defaults(self):
        btn = validate_button({"type": "note"}, index=0)
        assert btn["note"] == 60
        assert btn["velocity_on"] == 127
        assert btn["velocity_off"] == 0

    def test_note_type_custom_velocity(self):
        btn = validate_button({"type": "note", "note": 36, "velocity_on": 100, "velocity_off": 0}, index=0)
        assert btn["velocity_on"] == 100
        assert btn["velocity_off"] == 0

    def test_note_type_no_cc_fields(self):
        btn = validate_button({"type": "note"}, index=0)
        assert "cc" not in btn
        assert "cc_on" not in btn
        assert "cc_off" not in btn

    def test_pc_type(self):
        btn = validate_button({"type": "pc", "program": 5}, index=0)
        assert btn["type"] == "pc"
        assert btn["program"] == 5

    def test_pc_type_default_program(self):
        btn = validate_button({"type": "pc"}, index=0)
        assert btn["program"] == 0

    def test_pc_type_no_cc_fields(self):
        btn = validate_button({"type": "pc"}, index=0)
        assert "cc" not in btn
        assert "cc_on" not in btn
        assert "cc_off" not in btn

    def test_pc_inc_type(self):
        btn = validate_button({"type": "pc_inc", "pc_step": 5}, index=0)
        assert btn["type"] == "pc_inc"
        assert btn["pc_step"] == 5

    def test_pc_dec_type(self):
        btn = validate_button({"type": "pc_dec", "pc_step": 2}, index=0)
        assert btn["type"] == "pc_dec"
        assert btn["pc_step"] == 2

    def test_pc_inc_dec_default_step(self):
        btn_inc = validate_button({"type": "pc_inc"}, index=0)
        btn_dec = validate_button({"type": "pc_dec"}, index=0)
        assert btn_inc["pc_step"] == 1
        assert btn_dec["pc_step"] == 1

    def test_pc_type_default_mode_is_flash(self):
        """PC button type defaults to flash mode, not toggle."""
        btn = validate_button({"type": "pc", "program": 0}, index=0)
        assert btn["mode"] == "flash"

    def test_pc_inc_dec_default_mode_is_flash(self):
        """PC inc/dec buttons default to flash mode."""
        btn_inc = validate_button({"type": "pc_inc"}, index=0)
        btn_dec = validate_button({"type": "pc_dec"}, index=0)
        assert btn_inc["mode"] == "flash"
        assert btn_dec["mode"] == "flash"

    def test_pc_type_accepts_toggle_mode(self):
        """PC button can be configured with toggle mode."""
        btn = validate_button({"type": "pc", "program": 0, "mode": "toggle"}, index=0)
        assert btn["mode"] == "toggle"

    def test_pc_type_accepts_momentary_mode(self):
        """PC button can be configured with momentary mode."""
        btn = validate_button({"type": "pc", "program": 0, "mode": "momentary"}, index=0)
        assert btn["mode"] == "momentary"

    def test_cc_type_default_mode_is_toggle(self):
        """CC button type still defaults to toggle mode."""
        btn = validate_button({"type": "cc", "cc": 20}, index=0)
        assert btn["mode"] == "toggle"

    def test_note_type_default_mode_is_toggle(self):
        """Note button type still defaults to toggle mode."""
        btn = validate_button({"type": "note", "note": 60}, index=0)
        assert btn["mode"] == "toggle"

    def test_pc_type_rejects_invalid_mode(self):
        """PC button with invalid mode falls back to flash."""
        btn = validate_button({"type": "pc", "program": 0, "mode": "invalid"}, index=0)
        assert btn["mode"] == "flash"

    def test_pc_type_preserves_flash_ms(self):
        """flash_ms from config must reach validated dict so firmware can read it."""
        btn = validate_button({"type": "pc", "program": 0, "flash_ms": 1000}, index=0)
        assert btn["flash_ms"] == 1000
        btn_inc = validate_button({"type": "pc_inc", "flash_ms": 750}, index=0)
        assert btn_inc["flash_ms"] == 750
        btn_dec = validate_button({"type": "pc_dec", "flash_ms": 500}, index=0)
        assert btn_dec["flash_ms"] == 500

    def test_pc_type_clamps_flash_ms(self):
        """flash_ms is clamped to schema range 50-5000."""
        btn_low = validate_button({"type": "pc", "program": 0, "flash_ms": 10}, index=0)
        assert btn_low["flash_ms"] == 50
        btn_high = validate_button({"type": "pc", "program": 0, "flash_ms": 99999}, index=0)
        assert btn_high["flash_ms"] == 5000

    def test_pc_type_omits_flash_ms_when_absent(self):
        """No flash_ms in config means the validated dict has no flash_ms key (firmware uses its default)."""
        btn = validate_button({"type": "pc", "program": 0}, index=0)
        assert "flash_ms" not in btn

    def test_invalid_type_falls_back_to_cc(self):
        btn = validate_button({"type": "invalid_type"}, index=0)
        assert btn["type"] == "cc"
        assert "cc" in btn

    def test_type_inherits_global_channel(self):
        btn = validate_button({"type": "note", "note": 48}, index=0, global_channel=3)
        assert btn["channel"] == 3

    def test_keytimes_works_with_note_type(self):
        btn = validate_button({"type": "note", "note": 60, "keytimes": 2}, index=0)
        assert btn["keytimes"] == 2

    def test_keytimes_works_with_cc_type(self):
        btn = validate_button({"type": "cc", "cc": 20, "keytimes": 3}, index=0)
        assert btn["keytimes"] == 3


class TestSelectMode:
    """Tests for select-mode (radio-group) button configuration. See docs/plans/2026-05-07-issue-43-select-mode.md."""

    # --- Acceptance: PC + CC with valid group ---

    def test_pc_select_mode_with_group_accepted(self):
        btn = validate_button({"type": "pc", "mode": "select", "select_group": "amp", "program": 5}, index=0)
        assert btn["mode"] == "select"
        assert btn["select_group"] == "amp"
        assert btn["select_repress"] == "resend"  # default
        assert btn["program"] == 5

    def test_cc_select_mode_with_group_accepted(self):
        btn = validate_button({"type": "cc", "mode": "select", "select_group": "ir", "cc": 30}, index=0)
        assert btn["mode"] == "select"
        assert btn["select_group"] == "ir"
        assert btn["select_repress"] == "resend"

    def test_select_group_trimmed(self):
        """Whitespace around group name is trimmed."""
        btn = validate_button({"type": "pc", "mode": "select", "select_group": "  amp  ", "program": 0}, index=0)
        assert btn["select_group"] == "amp"

    # --- Rejection: missing / empty group coerces mode away ---

    def test_select_mode_missing_group_coerces_to_default(self):
        """mode=select with no select_group: mode coerced back to type's default; select_* fields stripped."""
        btn = validate_button({"type": "pc", "mode": "select", "program": 0}, index=0)
        assert btn["mode"] == "flash"  # PC default
        assert "select_group" not in btn
        assert "select_repress" not in btn

    def test_select_mode_empty_group_coerces_to_default(self):
        btn = validate_button({"type": "cc", "mode": "select", "select_group": "", "cc": 20}, index=0)
        assert btn["mode"] == "toggle"  # CC default
        assert "select_group" not in btn
        assert "select_repress" not in btn

    def test_select_mode_whitespace_only_group_coerces_to_default(self):
        btn = validate_button({"type": "pc", "mode": "select", "select_group": "   ", "program": 0}, index=0)
        assert btn["mode"] == "flash"
        assert "select_group" not in btn

    def test_select_mode_non_string_group_coerces_to_default(self):
        btn = validate_button({"type": "pc", "mode": "select", "select_group": 42, "program": 0}, index=0)
        assert btn["mode"] == "flash"
        assert "select_group" not in btn

    # --- select_repress validation ---

    def test_select_repress_default_is_resend(self):
        btn = validate_button({"type": "pc", "mode": "select", "select_group": "g", "program": 0}, index=0)
        assert btn["select_repress"] == "resend"

    def test_select_repress_resend_accepted(self):
        btn = validate_button({"type": "pc", "mode": "select", "select_group": "g", "select_repress": "resend", "program": 0}, index=0)
        assert btn["select_repress"] == "resend"

    def test_select_repress_nothing_accepted(self):
        btn = validate_button({"type": "pc", "mode": "select", "select_group": "g", "select_repress": "nothing", "program": 0}, index=0)
        assert btn["select_repress"] == "nothing"

    def test_select_repress_deselect_accepted_on_cc(self):
        btn = validate_button({"type": "cc", "mode": "select", "select_group": "g", "select_repress": "deselect", "cc": 20}, index=0)
        assert btn["select_repress"] == "deselect"

    def test_select_repress_deselect_preserved_on_pc(self):
        """PC + deselect is preserved through validation; firmware will no-op until #47 lands."""
        btn = validate_button({"type": "pc", "mode": "select", "select_group": "g", "select_repress": "deselect", "program": 0}, index=0)
        assert btn["select_repress"] == "deselect"

    def test_select_repress_invalid_defaults_to_resend(self):
        btn = validate_button({"type": "pc", "mode": "select", "select_group": "g", "select_repress": "garbage", "program": 0}, index=0)
        assert btn["select_repress"] == "resend"

    # --- Rejection: select on disallowed types ---

    def test_select_mode_rejected_on_pc_inc(self):
        btn = validate_button({"type": "pc_inc", "mode": "select", "select_group": "g"}, index=0)
        assert btn["mode"] == "flash"  # pc_inc default
        assert "select_group" not in btn

    def test_select_mode_rejected_on_pc_dec(self):
        btn = validate_button({"type": "pc_dec", "mode": "select", "select_group": "g"}, index=0)
        assert btn["mode"] == "flash"
        assert "select_group" not in btn

    def test_select_mode_rejected_on_note(self):
        btn = validate_button({"type": "note", "mode": "select", "select_group": "g", "note": 60}, index=0)
        assert btn["mode"] == "toggle"  # note default
        assert "select_group" not in btn

    def test_select_mode_rejected_on_hid(self):
        btn = validate_button({"type": "hid", "color": "blue", "label": "K",
                               "mode": "select", "select_group": "g", "hid_key": "A"}, index=0)
        assert btn["mode"] == "toggle"  # hid default
        assert "select_group" not in btn

    # --- Rejection: multi-keytime + select ---

    def test_select_mode_rejects_multi_keytime(self):
        """select + keytimes>1 coerces mode back to default; select_* stripped."""
        btn = validate_button({
            "type": "pc",
            "mode": "select",
            "select_group": "g",
            "program": 5,
            "keytimes": 3,
            "states": [{"program": 1}, {"program": 2}, {"program": 3}],
        }, index=0)
        assert btn["mode"] == "flash"
        assert "select_group" not in btn
        assert "select_repress" not in btn

    def test_select_mode_with_keytimes_one_accepted(self):
        """keytimes=1 (default) with select is fine."""
        btn = validate_button({"type": "pc", "mode": "select", "select_group": "g", "program": 0, "keytimes": 1}, index=0)
        assert btn["mode"] == "select"
        assert btn["select_group"] == "g"

    # --- Strip when mode != select ---

    def test_select_group_stripped_when_mode_flash(self):
        btn = validate_button({"type": "pc", "mode": "flash", "select_group": "g", "select_repress": "nothing", "program": 0}, index=0)
        assert btn["mode"] == "flash"
        assert "select_group" not in btn
        assert "select_repress" not in btn

    def test_select_group_stripped_when_mode_toggle(self):
        btn = validate_button({"type": "cc", "mode": "toggle", "select_group": "g", "cc": 20}, index=0)
        assert btn["mode"] == "toggle"
        assert "select_group" not in btn
        assert "select_repress" not in btn

    def test_select_group_stripped_when_mode_momentary(self):
        btn = validate_button({"type": "cc", "mode": "momentary", "select_group": "g", "cc": 20}, index=0)
        assert "select_group" not in btn
        assert "select_repress" not in btn


class TestValidateConfig:
    """Test validate_config function from core/config.py."""
    
    def test_extends_short_button_array(self):
        """Fills in missing buttons if fewer than button_count."""
        cfg = validate_config({"buttons": [{"label": "A"}]}, button_count=3)
        
        assert len(cfg["buttons"]) == 3
        assert cfg["buttons"][0]["label"] == "A"
        assert cfg["buttons"][1]["label"] == "2"
        assert cfg["buttons"][2]["label"] == "3"
    
    def test_preserves_extra_config_keys(self):
        """Keeps encoder, expression, etc."""
        cfg = validate_config({
            "buttons": [],
            "encoder": {"cc": 11},
            "custom": "value"
        }, button_count=2)
        
        assert cfg["encoder"] == {"cc": 11}
        assert cfg["custom"] == "value"
    
    def test_global_channel_default(self):
        """Global channel defaults to 0 (MIDI Ch 1)."""
        cfg = validate_config({"buttons": []}, button_count=2)
        assert cfg["global_channel"] == 0
    
    def test_global_channel_explicit(self):
        """Can set explicit global channel."""
        cfg = validate_config({"buttons": [], "global_channel": 7}, button_count=2)
        assert cfg["global_channel"] == 7
    
    def test_global_channel_clamped(self):
        """Global channel is clamped to 0-15."""
        cfg = validate_config({"buttons": [], "global_channel": 99}, button_count=1)
        assert cfg["global_channel"] == 0  # Invalid, should clamp to default
        
        cfg = validate_config({"buttons": [], "global_channel": -5}, button_count=1)
        assert cfg["global_channel"] == 0
    
    def test_buttons_inherit_global_channel(self):
        """Buttons inherit global channel when not specified."""
        cfg = validate_config({"buttons": [{}], "global_channel": 3}, button_count=1)
        assert cfg["buttons"][0]["channel"] == 3


class TestEncoderConfig:
    """Test get_encoder_config from core/config.py."""
    
    def test_defaults_when_missing(self):
        """Returns sensible defaults when encoder not in config."""
        enc = get_encoder_config({})
        
        assert enc["enabled"] == True
        assert enc["cc"] == 11
        assert enc["min"] == 0
        assert enc["max"] == 127
        assert enc["initial"] == 64
        assert enc["push"]["cc"] == 14
        assert enc["channel"] == 0  # Default channel
        assert enc["push"]["channel"] == 0
    
    def test_overrides_defaults(self):
        """Config values override defaults."""
        enc = get_encoder_config({
            "encoder": {
                "cc": 55,
                "steps": 5,
                "push": {"cc": 77, "mode": "toggle"}
            }
        })
        
        assert enc["cc"] == 55
        assert enc["steps"] == 5
        assert enc["push"]["cc"] == 77
        assert enc["push"]["mode"] == "toggle"
    
    def test_encoder_inherits_global_channel(self):
        """Encoder inherits global channel when not specified."""
        enc = get_encoder_config({"global_channel": 8})
        assert enc["channel"] == 8
        assert enc["push"]["channel"] == 8
    
    def test_encoder_channel_override(self):
        """Encoder can override global channel."""
        enc = get_encoder_config({
            "global_channel": 5,
            "encoder": {"channel": 12}
        })
        assert enc["channel"] == 12
    
    def test_encoder_push_cc_values(self):
        """Encoder push can have custom cc_on and cc_off values."""
        enc = get_encoder_config({
            "encoder": {
                "push": {
                    "cc_on": 100,
                    "cc_off": 20
                }
            }
        })
        assert enc["push"]["cc_on"] == 100
        assert enc["push"]["cc_off"] == 20
    
    def test_encoder_push_cc_values_defaults(self):
        """Encoder push defaults to cc_on=127 and cc_off=0."""
        enc = get_encoder_config({"encoder": {"push": {}}})
        assert enc["push"]["cc_on"] == 127
        assert enc["push"]["cc_off"] == 0


class TestGetButtonStateConfig:
    def test_no_states_returns_base_cc_config(self):
        btn = {"type": "cc", "cc": 20, "cc_on": 127, "cc_off": 0, "color": "white"}
        result = get_button_state_config(btn, 1)
        assert result["cc"] == 20
        assert result["cc_on"] == 127
        assert result["cc_off"] == 0

    def test_state_overrides_cc_on(self):
        btn = {"type": "cc", "cc": 20, "cc_on": 127, "cc_off": 0,
               "states": [{"cc_on": 64}, {"cc_on": 96}]}
        assert get_button_state_config(btn, 1)["cc_on"] == 64
        assert get_button_state_config(btn, 2)["cc_on"] == 96

    def test_state_cc_falls_back_to_base(self):
        btn = {"type": "cc", "cc": 20, "cc_on": 127, "states": [{"cc_on": 64}]}
        result = get_button_state_config(btn, 1)
        assert result["cc"] == 20       # fallback
        assert result["cc_on"] == 64    # override

    def test_keytime_out_of_range_falls_back(self):
        btn = {"type": "cc", "cc": 20, "cc_on": 127, "states": [{"cc_on": 64}]}
        result = get_button_state_config(btn, 5)
        assert result["cc_on"] == 127   # base

    def test_note_state_overrides(self):
        btn = {"type": "note", "note": 60, "velocity_on": 127, "velocity_off": 0,
               "states": [{"note": 62, "velocity_on": 100}]}
        result = get_button_state_config(btn, 1)
        assert result["note"] == 62
        assert result["velocity_on"] == 100
        assert result["velocity_off"] == 0  # fallback

    def test_color_overridable_for_all_types(self):
        btn = {"type": "cc", "cc": 20, "cc_on": 127, "color": "blue",
               "states": [{"color": "cyan"}]}
        assert get_button_state_config(btn, 1)["color"] == "cyan"

    def test_pc_type_returns_base_program(self):
        btn = {"type": "pc", "program": 5, "color": "green",
               "states": [{"color": "red"}]}
        result = get_button_state_config(btn, 1)
        assert result["program"] == 5
        assert result["color"] == "red"

    def test_pc_state_overrides_program(self):
        btn = {"type": "pc", "program": 5, "states": [{"program": 10}, {"program": 20}]}
        assert get_button_state_config(btn, 1)["program"] == 10
        assert get_button_state_config(btn, 2)["program"] == 20

    def test_pc_inc_state_overrides_pc_step(self):
        btn = {"type": "pc_inc", "pc_step": 1, "states": [{"pc_step": 5}]}
        assert get_button_state_config(btn, 1)["pc_step"] == 5

    def test_pc_dec_state_overrides_pc_step(self):
        btn = {"type": "pc_dec", "pc_step": 1, "states": [{"pc_step": 3}]}
        assert get_button_state_config(btn, 1)["pc_step"] == 3

    def test_no_color_key_in_result_when_not_in_config(self):
        """color absent from btn_config means no color key in result — callers must use .get()."""
        btn = {"type": "cc", "cc": 20}
        result = get_button_state_config(btn, 1)
        assert "color" not in result


class TestHidButtonType:
    """Tests for HID button type configuration."""

    def test_hid_type_recognized(self):
        btn = validate_button({"type": "hid", "color": "blue", "label": "KEY-A",
                               "hid_action": "send", "hid_key": "A"}, index=0)
        assert btn["type"] == "hid"

    def test_hid_type_default_action(self):
        btn = validate_button({"type": "hid", "color": "blue", "label": "K",
                               "hid_key": "A"}, index=0)
        assert btn["hid_action"] == "send"

    def test_hid_action_send(self):
        btn = validate_button({"type": "hid", "color": "blue", "label": "K",
                               "hid_action": "send", "hid_key": "A"}, index=0)
        assert btn["hid_action"] == "send"

    def test_hid_action_press(self):
        btn = validate_button({"type": "hid", "color": "blue", "label": "K",
                               "hid_action": "press", "hid_key": "A"}, index=0)
        assert btn["hid_action"] == "press"

    def test_hid_action_release(self):
        btn = validate_button({"type": "hid", "color": "blue", "label": "K",
                               "hid_action": "release", "hid_key": "all"}, index=0)
        assert btn["hid_action"] == "release"
        assert btn["hid_key"] == "all"

    def test_hid_action_delay(self):
        btn = validate_button({"type": "hid", "color": "blue", "label": "DLY",
                               "hid_action": "delay", "hid_delay_ms": 100}, index=0)
        assert btn["hid_action"] == "delay"
        assert btn["hid_delay_ms"] == 100

    def test_hid_invalid_action_defaults_to_send(self):
        btn = validate_button({"type": "hid", "color": "blue", "label": "K",
                               "hid_action": "invalid_action"}, index=0)
        assert btn["hid_action"] == "send"

    def test_hid_modifier_ctrl(self):
        btn = validate_button({"type": "hid", "color": "blue", "label": "K",
                               "hid_key": "S", "hid_modifier": "ctrl"}, index=0)
        assert btn["hid_modifier"] == "ctrl"

    def test_hid_modifier_shift(self):
        btn = validate_button({"type": "hid", "color": "blue", "label": "K",
                               "hid_key": "A", "hid_modifier": "shift"}, index=0)
        assert btn["hid_modifier"] == "shift"

    def test_hid_modifier_alt(self):
        btn = validate_button({"type": "hid", "color": "blue", "label": "K",
                               "hid_key": "F4", "hid_modifier": "alt"}, index=0)
        assert btn["hid_modifier"] == "alt"

    def test_hid_modifier_option(self):
        btn = validate_button({"type": "hid", "color": "blue", "label": "K",
                               "hid_key": "A", "hid_modifier": "option"}, index=0)
        assert btn["hid_modifier"] == "option"

    def test_hid_modifier_windows(self):
        btn = validate_button({"type": "hid", "color": "blue", "label": "K",
                               "hid_key": "D", "hid_modifier": "windows"}, index=0)
        assert btn["hid_modifier"] == "windows"

    def test_hid_invalid_modifier_dropped(self):
        btn = validate_button({"type": "hid", "color": "blue", "label": "K",
                               "hid_key": "A", "hid_modifier": "super"}, index=0)
        assert "hid_modifier" not in btn

    def test_hid_delay_ms_clamped_high(self):
        btn = validate_button({"type": "hid", "color": "blue", "label": "K",
                               "hid_action": "delay", "hid_delay_ms": 99999}, index=0)
        assert btn["hid_delay_ms"] == 5000

    def test_hid_delay_ms_clamped_low(self):
        btn = validate_button({"type": "hid", "color": "blue", "label": "K",
                               "hid_action": "delay", "hid_delay_ms": 0}, index=0)
        assert btn["hid_delay_ms"] == 1

    def test_hid_no_cc_fields(self):
        btn = validate_button({"type": "hid", "color": "blue", "label": "K",
                               "hid_key": "A"}, index=0)
        assert "cc" not in btn
        assert "cc_on" not in btn

    def test_hid_no_note_fields(self):
        btn = validate_button({"type": "hid", "color": "blue", "label": "K",
                               "hid_key": "A"}, index=0)
        assert "note" not in btn

    def test_hid_no_pc_fields(self):
        btn = validate_button({"type": "hid", "color": "blue", "label": "K",
                               "hid_key": "A"}, index=0)
        assert "program" not in btn

    def test_hid_with_keytimes_and_states(self):
        btn = validate_button({
            "type": "hid",
            "color": "blue",
            "label": "K",
            "hid_key": "A",
            "keytimes": 2,
            "states": [
                {"hid_key": "B", "hid_modifier": "ctrl"},
                {"hid_key": "C"},
            ],
        }, index=0)
        assert btn["keytimes"] == 2
        assert btn["states"][0]["hid_key"] == "B"
        assert btn["states"][0]["hid_modifier"] == "ctrl"
        assert btn["states"][1]["hid_key"] == "C"

    def test_hid_state_delay_ms_clamped(self):
        btn = validate_button({
            "type": "hid",
            "color": "blue",
            "label": "K",
            "hid_action": "delay",
            "keytimes": 2,
            "states": [{"hid_delay_ms": 0}, {"hid_delay_ms": 100}],
        }, index=0)
        assert btn["states"][0]["hid_delay_ms"] == 1
        assert btn["states"][1]["hid_delay_ms"] == 100

    def test_hid_inherits_global_channel(self):
        btn = validate_button({"type": "hid", "color": "blue", "label": "K",
                               "hid_key": "A"}, index=0, global_channel=3)
        assert btn["channel"] == 3
