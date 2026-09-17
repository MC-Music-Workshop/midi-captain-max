"""
Tests for find_cc_rx_action from core/midi_rx.py (#163).

Pure decision function extracted from _process_midi_msg's CC branch so the
RX button-matching rules are unit-testable (code.py itself can't be imported
under pytest — unguarded main loop). Covers the #155 follow-up shielding fix:
a select-claimed CC must not fall through to non-select buttons.
"""

import sys
from pathlib import Path

# Add firmware/dev to path
FIRMWARE_DIR = Path(__file__).parent.parent / "firmware" / "dev"
sys.path.insert(0, str(FIRMWARE_DIR))

from core.midi_rx import find_cc_rx_action


def select_btn(cc, cc_on=127, group="g", channel=0):
    return {
        "type": "cc", "mode": "select", "cc": cc, "cc_on": cc_on,
        "cc_off": 0, "select_group": group, "channel": channel,
    }


def toggle_btn(cc, channel=0, cc_on=127, cc_off=0):
    return {
        "type": "cc", "mode": "toggle", "cc": cc, "cc_on": cc_on,
        "cc_off": cc_off, "channel": channel,
    }


class TestSelectActivation:
    def test_exact_cc_on_activates_select(self):
        """Helix snapshots: same CC, distinct cc_on values select the member."""
        buttons = [select_btn(69, cc_on=0), select_btn(69, cc_on=1), select_btn(69, cc_on=2)]
        assert find_cc_rx_action(buttons, 69, 1, 0) == ("select", 1)
        assert find_cc_rx_action(buttons, 69, 2, 0) == ("select", 2)

    def test_first_matching_select_wins(self):
        """Two selects with identical cc_on: first in list wins (stable order)."""
        buttons = [select_btn(69, cc_on=5), select_btn(69, cc_on=5)]
        assert find_cc_rx_action(buttons, 69, 5, 0) == ("select", 0)


class TestShielding:
    def test_select_shields_downstream_non_select(self):
        """#163 blocker: non-cc_on value on a select-claimed CC must NOT
        fall through to a later non-select button sharing that CC."""
        buttons = [select_btn(20, cc_on=127), toggle_btn(20)]
        assert find_cc_rx_action(buttons, 20, 64, 0) == ("ignored", None)

    def test_lone_select_non_matching_value_ignored(self):
        buttons = [select_btn(20, cc_on=127)]
        assert find_cc_rx_action(buttons, 20, 64, 0) == ("ignored", None)

    def test_non_select_before_select_still_wins(self):
        """Pre-#155 behavior: first matching button consumes; a non-select
        button listed before the select one keeps its state path."""
        buttons = [toggle_btn(20), select_btn(20, cc_on=127)]
        assert find_cc_rx_action(buttons, 20, 64, 0) == ("state", 0)

    def test_shield_does_not_leak_across_ccs(self):
        """A select claim on CC 20 must not shield a non-select button on CC 21."""
        buttons = [select_btn(20, cc_on=127), toggle_btn(21)]
        assert find_cc_rx_action(buttons, 21, 64, 0) == ("state", 1)


class TestStateRouting:
    def test_plain_button_gets_state_action(self):
        buttons = [toggle_btn(20)]
        assert find_cc_rx_action(buttons, 20, 64, 0) == ("state", 0)

    def test_no_cc_match_returns_none(self):
        buttons = [toggle_btn(20)]
        assert find_cc_rx_action(buttons, 21, 127, 0) == (None, None)

    def test_channel_mismatch_returns_none(self):
        buttons = [toggle_btn(20, channel=1)]
        assert find_cc_rx_action(buttons, 20, 127, 0) == (None, None)

    def test_non_cc_type_skipped(self):
        """Note/PC buttons never match the CC path, even with a stray cc key."""
        buttons = [{"type": "note", "note": 60, "cc": 20, "channel": 0}, toggle_btn(20)]
        assert find_cc_rx_action(buttons, 20, 64, 0) == ("state", 1)

    def test_missing_type_defaults_to_cc(self):
        """Buttons without an explicit type are treated as cc (legacy configs)."""
        buttons = [{"mode": "toggle", "cc": 20, "channel": 0}]
        assert find_cc_rx_action(buttons, 20, 64, 0) == ("state", 0)


def cc_step_btn(cc, channel=0, **over):
    btn = {"type": "cc_inc", "cc": cc, "channel": channel, "cc_step": 1,
           "cc_min": 0, "cc_max": 127, "cc_wrap": True}
    btn.update(over)
    return btn


class TestCcStepRouting:
    """cc_inc/cc_dec buttons (#11) claim their (cc, channel) for the shared value."""

    def test_cc_step_button_claims_cc(self):
        buttons = [cc_step_btn(30)]
        assert find_cc_rx_action(buttons, 30, 64, 0) == ("cc_step", 0)

    def test_any_value_matches_no_gate(self):
        buttons = [cc_step_btn(30)]
        for val in (0, 1, 63, 64, 127):
            assert find_cc_rx_action(buttons, 30, val, 0) == ("cc_step", 0)

    def test_cc_dec_matches_too(self):
        buttons = [cc_step_btn(30, type="cc_dec")]
        assert find_cc_rx_action(buttons, 30, 5, 0) == ("cc_step", 0)

    def test_first_button_on_key_wins(self):
        """inc + dec on one key: the first one is returned; code.py refreshes both."""
        buttons = [toggle_btn(20), cc_step_btn(30), cc_step_btn(30, type="cc_dec")]
        assert find_cc_rx_action(buttons, 30, 5, 0) == ("cc_step", 1)

    def test_channel_mismatch_skips(self):
        buttons = [cc_step_btn(30, channel=3), toggle_btn(30)]
        assert find_cc_rx_action(buttons, 30, 64, 0) == ("state", 1)

    def test_keytimes_button_with_cc_step_fields_matches(self):
        """A keytimes button whose entries fire cc_inc carries the cc-step fields
        (validator) and must claim its CC like a plain cc_inc button."""
        buttons = [{"mode": "keytimes", "type": "cc", "cc": 30, "channel": 0,
                    "cc_slots": 4, "cc_min": 0, "cc_max": 127, "cc_wrap": True,
                    "short": [{"down": [{"type": "cc_inc"}]}]}]
        assert find_cc_rx_action(buttons, 30, 64, 0) == ("cc_step", 0)

    def test_plain_keytimes_button_still_ignored(self):
        buttons = [{"mode": "keytimes", "type": "cc", "channel": 0,
                    "short": [{"down": [{"type": "cc", "cc": 30, "value": 127}]}]}]
        assert find_cc_rx_action(buttons, 30, 64, 0) == (None, None)

    def test_cc_step_does_not_shield_other_ccs(self):
        buttons = [cc_step_btn(30), toggle_btn(31)]
        assert find_cc_rx_action(buttons, 31, 64, 0) == ("state", 1)


class TestCcReceive:
    """cc_receive: listen on a different CC than the one sent.

    Motivating case: a looper plugin exposing a momentary play/stop *command*
    input and a separate read-only is-playing *state* output. The button sends
    the command on cc and takes its LED from the state CC.
    """

    def test_listens_on_cc_receive_not_cc(self):
        btn = toggle_btn(7)
        btn["cc_receive"] = 20
        assert find_cc_rx_action([btn], 20, 127, 0) == ("state", 0)

    def test_sent_cc_no_longer_matches(self):
        """The command CC comes back from a synced host widget carrying press
        noise, not playback state — it must not drive the LED."""
        btn = toggle_btn(7)
        btn["cc_receive"] = 20
        assert find_cc_rx_action([btn], 7, 127, 0) == (None, None)

    def test_channel_still_applies(self):
        btn = toggle_btn(7, channel=1)
        btn["cc_receive"] = 20
        assert find_cc_rx_action([btn], 20, 127, 0) == (None, None)
        assert find_cc_rx_action([btn], 20, 127, 1) == ("state", 0)

    def test_absent_cc_receive_keeps_bidirectional_default(self):
        assert find_cc_rx_action([toggle_btn(7)], 7, 127, 0) == ("state", 0)

    def test_shielding_follows_the_listened_on_cc(self):
        """A select button claiming CC 20 shields a listener on CC 20, even
        though that listener sends on 7."""
        listener = toggle_btn(7)
        listener["cc_receive"] = 20
        buttons = [select_btn(20, cc_on=1), listener]
        assert find_cc_rx_action(buttons, 20, 99, 0) == ("ignored", None)
        assert find_cc_rx_action(buttons, 20, 1, 0) == ("select", 0)

    def test_two_buttons_can_send_same_cc_and_listen_apart(self):
        a = toggle_btn(7)
        a["cc_receive"] = 20
        b = toggle_btn(7)
        b["cc_receive"] = 21
        assert find_cc_rx_action([a, b], 20, 127, 0) == ("state", 0)
        assert find_cc_rx_action([a, b], 21, 127, 0) == ("state", 1)
