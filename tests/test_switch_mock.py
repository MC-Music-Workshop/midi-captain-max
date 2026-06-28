"""
Tests for the switch/digitalio mock.
"""

import pytest
import sys
from pathlib import Path

# Add firmware/dev to path
FIRMWARE_DIR = Path(__file__).parent.parent / "firmware" / "dev"
sys.path.insert(0, str(FIRMWARE_DIR))
from core.button import Switch
from tests.mocks import digitalio as mock_digitalio
from tests.mocks import board


class TestSwitchMock:
    """Verify the mock switch inputs work correctly."""
    
    def test_initial_state_is_released(self, mock_switches):
        """All switches should start in released (high) state."""
        for sw in mock_switches:
            assert sw.value == True  # Active-low: high = not pressed
    
    def test_simulate_press(self, mock_switches):
        """Can simulate a button press."""
        mock_switches[1].simulate_press()
        assert mock_switches[1].value == False  # Active-low: low = pressed
        assert mock_switches[2].value == True   # Others unchanged
    
    def test_simulate_release(self, mock_switches):
        """Can simulate a button release."""
        mock_switches[1].simulate_press()
        mock_switches[1].simulate_release()
        assert mock_switches[1].value == True
    
    def test_multiple_presses(self, mock_switches):
        """Can press multiple buttons simultaneously."""
        mock_switches[1].simulate_press()
        mock_switches[6].simulate_press()
        
        assert mock_switches[1].value == False
        assert mock_switches[6].value == False
        assert mock_switches[2].value == True  # Others still released


class TestButtonDebounce:
    """Test button debouncing logic (to be extracted from code.py)."""
    
    # This is a placeholder for debounce logic that should be extracted
    # into a testable module. For now, just demonstrate the pattern.
    
    def test_placeholder(self):
        """Placeholder test - implement when debounce is extracted."""
        # TODO: Extract ButtonState class from code.py and test here
        assert True


class TestSwitchEdgeDetection:
    """Regression tests for Switch.changed() startup behavior (issue #112)."""

    def _make_switch(self):
        return Switch(board.GP0, digitalio_module=mock_digitalio)

    def test_no_phantom_edge_at_boot(self):
        """First poll of an untouched switch reports no change (#112).

        Previously last_state initialized to True while pressed=False, so the
        first changed() reported a phantom release edge that fired startup CC=0
        on momentary/encoder buttons.
        """
        sw = self._make_switch()
        changed, pressed = sw.changed()
        assert changed is False
        assert pressed is False

    def test_first_press_registers(self):
        """A press landing before the first poll still produces a press edge."""
        sw = self._make_switch()
        sw.io.simulate_press()
        changed, pressed = sw.changed()
        assert changed is True
        assert pressed is True

    def test_press_release_cycle(self):
        """Normal press then release produces two edges."""
        sw = self._make_switch()
        sw.changed()  # boot poll, no edge

        sw.io.simulate_press()
        assert sw.changed() == (True, True)

        sw.io.simulate_release()
        assert sw.changed() == (True, False)
