"""
Tests for the ButtonState class from core/button.py.
"""

import pytest
import sys
from pathlib import Path

# Add firmware/dev to path
FIRMWARE_DIR = Path(__file__).parent.parent / "firmware" / "dev"
sys.path.insert(0, str(FIRMWARE_DIR))

from core.button import ButtonState


class TestButtonStateToggle:
    """Tests for toggle mode buttons."""
    
    def test_initial_state_off(self):
        """Button starts in off state by default."""
        btn = ButtonState(cc=20)
        assert btn.state == False
    
    def test_initial_state_on(self):
        """Can start button in on state."""
        btn = ButtonState(cc=20, initial_state=True)
        assert btn.state == True
    
    def test_press_toggles_on(self):
        """First press turns button on."""
        btn = ButtonState(cc=20, mode="toggle")
        changed, state, value = btn.on_press()
        
        assert changed == True
        assert state == True
        assert value == 127
        assert btn.state == True
    
    def test_press_toggles_off(self):
        """Second press turns button off."""
        btn = ButtonState(cc=20, mode="toggle", initial_state=True)
        changed, state, value = btn.on_press()
        
        assert changed == True
        assert state == False
        assert value == 0
        assert btn.state == False
    
    def test_release_does_nothing_in_toggle(self):
        """Release has no effect in toggle mode."""
        btn = ButtonState(cc=20, mode="toggle")
        btn.on_press()  # Turn on
        
        changed, state, value = btn.on_release()
        
        assert changed == False
        assert state == True  # Still on
        assert value is None
        assert btn.state == True


class TestButtonStateMomentary:
    """Tests for momentary mode buttons."""
    
    def test_press_turns_on(self):
        """Press turns button on."""
        btn = ButtonState(cc=20, mode="momentary")
        changed, state, value = btn.on_press()
        
        assert changed == True
        assert state == True
        assert value == 127
    
    def test_release_turns_off(self):
        """Release turns button off."""
        btn = ButtonState(cc=20, mode="momentary")
        btn.on_press()
        changed, state, value = btn.on_release()
        
        assert changed == True
        assert state == False
        assert value == 0


class TestButtonStateMidiReceive:
    """Tests for host override via MIDI."""
    
    def test_high_value_turns_on(self):
        """CC value > 63 turns button on."""
        btn = ButtonState(cc=20)
        result = btn.on_midi_receive(127)
        
        assert result == True
        assert btn.state == True
    
    def test_low_value_turns_off(self):
        """CC value <= 63 turns button off."""
        btn = ButtonState(cc=20, initial_state=True)
        result = btn.on_midi_receive(0)
        
        assert result == False
        assert btn.state == False
    
    def test_threshold_at_64(self):
        """Value 64 is on, 63 is off (default cc_on/cc_off)."""
        btn = ButtonState(cc=20)
        
        btn.on_midi_receive(63)
        assert btn.state == False
        
        btn.on_midi_receive(64)
        assert btn.state == True

    def test_custom_cc_on_below_threshold(self):
        """Exact cc_on match turns on even when below 64."""
        btn = ButtonState(cc=20)
        result = btn.on_midi_receive(50, cc_on=50, cc_off=10)

        assert result == True
        assert btn.state == True

    def test_custom_cc_off_below_threshold(self):
        """Exact cc_off match turns off even when above 0."""
        btn = ButtonState(cc=20, initial_state=True)
        result = btn.on_midi_receive(10, cc_on=100, cc_off=10)

        assert result == False
        assert btn.state == False
    
    def test_host_override_persists(self):
        """Host can override local toggle state."""
        btn = ButtonState(cc=20, mode="toggle", initial_state=True)
        
        # Host says off
        btn.on_midi_receive(0)
        assert btn.state == False
        
        # Local press toggles back on
        btn.on_press()
        assert btn.state == True


class TestButtonStateKeytimes:
    """Tests for keytimes (multi-press cycling)."""
    
    def test_keytimes_default_is_one(self):
        """Button defaults to keytimes=1 (no cycling)."""
        btn = ButtonState(cc=20)
        assert btn.keytimes == 1
        assert btn.current_keytime == 1
    
    def test_keytimes_clamps_to_valid_range(self):
        """Keytimes is clamped to 1-99."""
        btn_low = ButtonState(cc=20, keytimes=0)
        assert btn_low.keytimes == 1
        
        btn_high = ButtonState(cc=20, keytimes=150)
        assert btn_high.keytimes == 99
    
    def test_keytimes_cycles_through_states(self):
        """Button cycles through keytime states on repeated presses."""
        btn = ButtonState(cc=20, mode="toggle", keytimes=3)
        
        # Initial state
        assert btn.get_keytime() == 1
        
        # First press -> keytime 2
        btn.on_press()
        assert btn.get_keytime() == 2
        assert btn.state == True
        
        # Second press -> keytime 3
        btn.on_press()
        assert btn.get_keytime() == 3
        assert btn.state == True
        
        # Third press -> cycles back to keytime 1
        btn.on_press()
        assert btn.get_keytime() == 1
        assert btn.state == True
    
    def test_keytimes_with_momentary_mode(self):
        """Keytimes work with momentary mode."""
        btn = ButtonState(cc=20, mode="momentary", keytimes=2)
        
        assert btn.get_keytime() == 1
        
        # Press advances keytime
        btn.on_press()
        assert btn.get_keytime() == 2
        assert btn.state == True
        
        # Release doesn't affect keytime
        btn.on_release()
        assert btn.get_keytime() == 2
        assert btn.state == False
        
        # Next press cycles back to 1
        btn.on_press()
        assert btn.get_keytime() == 1
    
    def test_reset_keytime(self):
        """reset_keytime() returns to state 1."""
        btn = ButtonState(cc=20, keytimes=5)
        
        # Advance to state 3
        btn.on_press()
        btn.on_press()
        assert btn.get_keytime() == 3
        
        # Reset
        btn.reset_keytime()
        assert btn.get_keytime() == 1
        assert btn.state == False
    
    def test_keytimes_one_behaves_as_standard_toggle(self):
        """keytimes=1 maintains standard toggle behavior."""
        btn = ButtonState(cc=20, mode="toggle", keytimes=1)

        # Standard toggle on/off
        btn.on_press()
        assert btn.state == True
        assert btn.get_keytime() == 1

        btn.on_press()
        assert btn.state == False
        assert btn.get_keytime() == 1

    def test_keytimes_toggle_always_stays_on(self):
        """When keytimes > 1, toggle mode always stays on — it cycles states, never turns off."""
        btn = ButtonState(cc=20, mode="toggle", keytimes=3)
        btn.on_press()
        assert btn.state == True   # press 1 → on, keytime 2
        btn.on_press()
        assert btn.state == True   # press 2 → still on, keytime 3
        btn.on_press()
        assert btn.state == True   # press 3 → still on, keytime cycles back to 1


class TestAdvanceKeytime:
    """Tests for the advance_keytime() method."""

    def test_advance_keytime_increments_position(self):
        btn = ButtonState(cc=20, keytimes=3)
        btn.advance_keytime()
        assert btn.get_keytime() == 2

    def test_advance_keytime_wraps_at_max(self):
        btn = ButtonState(cc=20, keytimes=3)
        btn.advance_keytime()
        btn.advance_keytime()
        btn.advance_keytime()
        assert btn.get_keytime() == 1

    def test_advance_keytime_no_op_when_keytimes_is_one(self):
        btn = ButtonState(cc=20, keytimes=1)
        btn.advance_keytime()
        assert btn.get_keytime() == 1

    def test_on_press_toggle_uses_advance_keytime(self):
        """on_press() in toggle mode should call advance_keytime() internally."""
        btn = ButtonState(cc=20, mode="toggle", keytimes=3)
        btn.advance_keytime()  # → 2
        btn.on_press()         # should also advance → 3
        assert btn.get_keytime() == 3

    def test_on_press_momentary_uses_advance_keytime(self):
        """on_press() in momentary mode should call advance_keytime() internally."""
        btn = ButtonState(cc=20, mode="momentary", keytimes=2)
        btn.advance_keytime()  # → 2
        btn.on_press()         # should also advance → wrap to 1
        assert btn.get_keytime() == 1
