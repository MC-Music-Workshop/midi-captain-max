"""
A switch held across a page change belongs to the page it was pressed on: its release
must not be dispatched through the new page's button at that position (#223 review).

Before the fix, releasing a page_jump footswitch fired the new page's momentary CC OFF
(e.g. CC99=0) without its ON ever being sent, which can stop an unrelated action on the
host. Uses the real code.py via the `boot` fixture (tests/firmware_harness.py).
"""

from tests.firmware_harness import ControlChange, cc

PUSH = 0  # STD10 switch index of the encoder push


def _buttons(**overrides):
    btns = [{"label": str(i + 1), "cc": 20 + i, "color": "white"} for i in range(10)]
    for i, b in overrides.items():
        btns[int(i[1:])] = b
    return btns


def _page(buttons, push=None):
    page = {"buttons": buttons}
    if push is not None:
        page["encoder"] = {"enabled": True, "cc": 11, "label": "ENC", "push": dict({"enabled": True, "label": "P"}, **push)}
    return page


MOMENTARY_99 = {"label": "M99", "color": "white", "cc": 99, "mode": "momentary"}


def test_release_of_page_jump_footswitch_is_not_sent_to_new_page(boot):
    jump = {"label": "GO2", "color": "white", "type": "page_jump", "page": 1}
    pedal = boot({"device": "std10", "pages": [_page(_buttons(b0=jump)), _page(_buttons(b0=MOMENTARY_99))]})
    pedal.press(1)
    assert pedal["config"]["active_page"] == 1
    pedal.release(1)
    assert pedal.sent() == []  # was [CC99=0]
    pedal.tap(1)  # the next full press is the new page's button
    assert pedal.sent() == [cc(99, 127), cc(99, 0)]


def test_release_of_page_switching_encoder_push_is_not_sent_to_new_page(boot):
    pedal = boot({"device": "std10", "pages": [
        _page(_buttons(), push={"type": "page_inc"}),
        _page(_buttons(), push={"cc": 99, "mode": "momentary"})]})
    pedal.press(PUSH)
    assert pedal["config"]["active_page"] == 1
    pedal.release(PUSH)
    assert pedal.sent() == []
    pedal.tap(PUSH)
    assert pedal.sent() == [cc(99, 127), cc(99, 0)]


def test_long_press_page_gesture_release_is_not_sent_to_new_page(boot):
    """OEM gesture: page_inc in a keytimes button's long[]; the page changes mid-hold."""
    gesture = {"label": "NEXT", "color": "white", "mode": "keytimes",
               "short": [{"down": [{"type": "cc", "cc": 40, "value": 1}]}],
               "long": [{"down": [{"type": "page_inc"}]}]}
    pedal = boot({"device": "std10", "pages": [_page(_buttons(b9=gesture)), _page(_buttons(b9=MOMENTARY_99))]})
    pedal.press(10)
    pedal.sent()  # the short entry's CC40 fires on press; not under test here
    pedal.advance(1.0)  # past the 500 ms threshold: long down -> page_inc while still held
    assert pedal["config"]["active_page"] == 1
    pedal.advance(0.2)  # still held on the new page: must not read as a fresh press
    pedal.release(10)
    pedal.advance(0.1)
    assert pedal.sent() == []  # was [CC99=127, CC99=0]


def test_held_switch_landing_on_keytimes_button_does_not_fire_it(boot):
    jump = {"label": "GO2", "color": "white", "type": "page_jump", "page": 1}
    kt = {"label": "KT", "color": "white", "mode": "keytimes",
          "short": [{"down": [{"type": "cc", "cc": 50, "value": 1}]}],
          "long": [{"down": [{"type": "cc", "cc": 51, "value": 1}]}]}
    pedal = boot({"device": "std10", "pages": [_page(_buttons(b0=jump)), _page(_buttons(b0=kt))]})
    pedal.press(1)
    pedal.advance(1.0)  # held past the long threshold on the new page
    pedal.release(1)
    pedal.advance(0.1)
    assert pedal.sent() == []
    pedal.tap(1)  # a real press on the new page fires its short entry
    assert pedal.sent() == [cc(50, 1)]


def test_switch_held_through_midi_page_change_is_ignored_until_released(boot):
    pedal = boot({"device": "std10", "page_control": {"enabled": True, "jump": {"cc": 100}},
                  "pages": [_page(_buttons(b0={"label": "M20", "color": "white", "cc": 20, "mode": "momentary"})),
                            _page(_buttons(b0=MOMENTARY_99))]})
    pedal.press(1)
    assert pedal.sent() == [cc(20, 127)]
    pedal.receive(ControlChange(100, 1, channel=0))  # host jumps to page 2
    pedal.loop()  # page switch drains at the end of handle_switches
    assert pedal["config"]["active_page"] == 1
    pedal.release(1)
    assert pedal.sent() == []  # not page 2's CC99=0
    pedal.tap(1)
    assert pedal.sent() == [cc(99, 127), cc(99, 0)]


def test_switch_not_held_works_normally_after_page_change(boot):
    jump = {"label": "GO2", "color": "white", "type": "page_jump", "page": 1}
    pedal = boot({"device": "std10", "pages": [_page(_buttons(b0=jump)), _page(_buttons(b1=MOMENTARY_99))]})
    pedal.tap(1)
    assert pedal["config"]["active_page"] == 1
    pedal.tap(2)  # footswitch 2 wasn't held during the switch
    assert pedal.sent() == [cc(99, 127), cc(99, 0)]
