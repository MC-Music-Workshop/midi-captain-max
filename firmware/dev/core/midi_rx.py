"""Pure decision logic for routing incoming MIDI CC messages to buttons.

Extracted from code.py's _process_midi_msg so the matching rules are
unit-testable (code.py can't be imported under pytest — unguarded main loop).
code.py owns all side effects (LEDs, display, select-group state); this module
only decides which button reacts and how.
"""


def find_cc_rx_action(buttons, cc, val, channel):
    """Decide how an incoming CC message maps onto the button list.

    Matching rules (#155 semantics + #163 shielding fix):
    - Buttons match on type=="cc" (default), cc number, and channel.
    - First matching non-select button gets the "state" action (its
      ButtonState.on_midi_receive decides on/off; see core/button.py — the
      exact cc_on/cc_off match there is the non-select twin of the select
      matching below).
    - A select-mode button activates ("select") only on an exact cc_on match;
      other values are ignored to avoid false activation. The scan continues
      past it because several select buttons may share one CC number and
      differ only by cc_on (e.g. Helix snapshots on CC 69).
    - Once a select button has claimed the CC, non-select buttons on that
      same CC are shielded: without this, a non-cc_on value would fall
      through and spuriously toggle them via the >63 fallback (#163).

    Args:
        buttons: List of validated button config dicts (active page)
        cc: Incoming CC number
        val: Incoming CC value (0-127)
        channel: Incoming MIDI channel (0-indexed)

    Returns:
        (action, index) tuple:
        - ("select", i): activate select button i and its group
        - ("state", i): feed val to button i's on_midi_receive
        - ("ignored", None): consumed by a select-claimed CC, no state change
        - (None, None): no button matched
    """
    select_claimed = False
    for i, btn in enumerate(buttons):
        if btn.get("type", "cc") != "cc":
            continue
        if btn.get("cc") != cc or btn.get("channel", 0) != channel:
            continue
        if btn.get("mode") == "select":
            if val == btn.get("cc_on", 127):
                return ("select", i)
            select_claimed = True
            continue
        if select_claimed:
            break
        return ("state", i)
    if select_claimed:
        return ("ignored", None)
    return (None, None)
