"""
Drives the STD10 encoder push (switch 0) through the real firmware/dev/code.py on
desktop mocks: the MIDI it sends, that no footswitch LED moves, and that it shares
state with footswitches like a button. Harness: tests/firmware_harness.py; the `boot`
fixture lives in tests/conftest.py.
"""

import json

import pytest

from tests.firmware_harness import FW, REPO, NoteOn, ProgramChange, ControlChange, cc

PUSH = 0  # switch index of the STD10 encoder push


def std10(push=None, buttons=None, encoder=True, pages=None):
    btns = [{"label": str(i + 1), "cc": 20 + i, "color": "white"} for i in range(10)]
    for i, b in (buttons or {}).items():
        btns[i] = b
    page = {"buttons": btns}
    if encoder:
        page["encoder"] = {"enabled": True, "cc": 11, "label": "ENC"}
        if push is not None:
            page["encoder"]["push"] = push
    cfg = {"device": "std10", "pages": [page] + (pages or [])}
    return cfg


# --- tests ------------------------------------------------------------------

def test_shipped_config_push_is_momentary_cc14(boot):
    pedal = boot(json.loads((FW / "config.json").read_text()))
    assert pedal["BUTTON_SLOTS"] == 11 and len(pedal["buttons"]) == 11
    leds = pedal.leds()
    pedal.press(PUSH)
    assert pedal.sent() == [cc(14, 127)]
    pedal.release(PUSH)
    assert pedal.sent() == [cc(14, 0)]
    assert pedal.leds() == leds  # no LED for the push


def test_page_without_push_gets_default_push(boot):
    pedal = boot(std10(push=None))
    pedal.tap(PUSH)
    assert pedal.sent() == [cc(14, 127), cc(14, 0)]


def test_legacy_toggle_push_with_custom_values(boot):
    pedal = boot(std10(push={"enabled": True, "cc": 77, "label": "P", "mode": "toggle",
                             "cc_on": 100, "cc_off": 20, "channel": 3}))
    pedal.tap(PUSH)
    pedal.tap(PUSH)
    assert pedal.sent() == [cc(77, 100, 3), cc(77, 20, 3)]


def test_legacy_flash_mode_push_is_momentary(boot):
    pedal = boot(std10(push={"enabled": True, "cc": 14, "label": "P", "mode": "flash"}))
    pedal.tap(PUSH)
    pedal.tap(PUSH)
    assert pedal.sent() == [cc(14, 127), cc(14, 0), cc(14, 127), cc(14, 0)]


def test_push_glyphs_preloaded(boot):
    pedal = boot(std10(push={"enabled": True, "label": "QZQZ", "type": "cc_inc", "cc": 40,
                             "cc_slots": 2, "cc_slot_names": ["JJ", "WW"]}))
    glyphs = pedal["_config_glyphs"](pedal["config"])
    assert set("QZJW") <= set(glyphs)


def test_disabled_push_sends_nothing(boot):
    pedal = boot(std10(push={"enabled": False, "cc": 14, "label": "P"}))
    assert len(pedal["buttons"]) == 10
    pedal.tap(PUSH)
    assert pedal.sent() == []
    pedal.tap(1)  # footswitch 1 still works
    assert pedal.sent() == [cc(20, 127)]


def test_footswitches_unaffected(boot):
    pedal = boot(std10(push={"enabled": True, "cc": 14, "label": "P"}))
    before = pedal.leds()
    pedal.tap(10)  # footswitch 10, toggle
    assert pedal.sent() == [cc(29, 127)]
    assert pedal.leds() != before  # its LED lit


def test_cc_inc_push_shares_value_with_footswitch(boot):
    step = {"type": "cc_inc", "cc": 30, "cc_step": 5, "cc_min": 0, "cc_max": 127}
    pedal = boot(std10(push=dict(step, enabled=True, label="UP"),
                       buttons={0: dict(step, label="UP", color="red")}))
    leds = pedal.leds()
    pedal.tap(PUSH)
    assert pedal.sent() == [cc(30, 5)]
    assert pedal.leds() != leds  # footswitch 1 shares the key, so it flashes
    pedal.tap(1)
    assert pedal.sent() == [cc(30, 10)]
    pedal.tap(PUSH)
    assert pedal.sent() == [cc(30, 15)]


def test_cc_inc_push_slots(boot):
    pedal = boot(std10(push={"enabled": True, "label": "AMP", "type": "cc_inc", "cc": 40,
                             "cc_slots": 4, "cc_slot_names": ["A", "B", "C", "D"]}))
    pedal.tap(PUSH)
    pedal.tap(PUSH)
    # slots of 0..127 / 4: middles 16, 48, 80, 112; starts in slot 0.
    assert pedal.sent() == [cc(40, 48), cc(40, 80)]


def test_pc_push_with_also_send(boot):
    pedal = boot(std10(push={"enabled": True, "label": "P", "type": "pc", "program": 5,
                             "messages_on": [{"type": "note", "note": 60, "velocity": 100}]}))
    leds = pedal.leds()
    pedal.tap(PUSH)
    assert pedal.sent() == [(ProgramChange(5), 0), (NoteOn(60, 100), 0)]
    pedal.clock.t += 1  # PC flash timer expires without touching an LED
    pedal["update_pc_flash_timers"]()
    assert pedal.leds() == leds


def test_momentary_push_messages_off_on_release(boot):
    pedal = boot(std10(push={"enabled": True, "label": "P", "cc": 50,
                             "messages_off": [{"type": "pc", "program": 9}]}))
    pedal.press(PUSH)
    assert pedal.sent() == [cc(50, 127)]
    pedal.release(PUSH)
    assert pedal.sent() == [cc(50, 0), (ProgramChange(9), 0)]


def test_select_push_dims_footswitch_sibling(boot):
    sel = {"type": "cc", "mode": "select", "select_group": "amps"}
    pedal = boot(std10(push=dict(sel, enabled=True, label="P", cc=60, cc_on=2),
                       buttons={0: dict(sel, label="A", color="red", cc=60, cc_on=1)}))
    states = pedal["button_states"]
    pedal.tap(1)
    lit = pedal.leds()
    assert states[0].state and not states[10].state
    pedal.tap(PUSH)
    assert pedal.sent()[-1] == cc(60, 2)
    assert states[10].state and not states[0].state
    assert pedal.leds() != lit  # footswitch 1 went to its off state


def test_keytimes_push_short_and_long(boot):
    pedal = boot(std10(push={"enabled": True, "label": "P", "mode": "keytimes",
                             "short": [{"down": [{"type": "cc", "cc": 41, "value": 1}]}],
                             "long": [{"down": [{"type": "cc", "cc": 42, "value": 2}]}]}))
    leds = pedal.leds()
    pedal.tap(PUSH)
    assert pedal.sent() == [cc(41, 1)]
    # Same as a footswitch: the short entry's down fires on press, the long
    # entry's down once the hold crosses the threshold.
    pedal.hold(PUSH, 2.0)
    assert pedal.sent() == [cc(41, 1), cc(42, 2)]
    assert pedal.leds() == leds


def test_hid_push_dispatches(boot):
    pedal = boot(std10(push={"enabled": True, "label": "P", "type": "hid", "hid_key": "A"}))
    calls = []
    pedal.ns["dispatch_hid"] = lambda *a: calls.append(a)
    leds = pedal.leds()
    pedal.tap(PUSH)
    assert calls and calls[0][2:4] == ("send", "A")
    pedal.clock.t += 1
    pedal["update_pc_flash_timers"]()
    assert pedal.leds() == leds


def test_page_jump_push_switches_page_and_push(boot):
    page2 = {"buttons": [{"label": str(i + 1), "cc": 50 + i, "color": "blue"} for i in range(10)],
             "encoder": {"enabled": True, "cc": 11, "label": "ENC",
                         "push": {"enabled": True, "label": "P2", "cc": 99}}}
    pedal = boot(std10(push={"enabled": True, "label": "P", "type": "page_jump", "page": 1},
                       pages=[page2]))
    pedal.tap(PUSH)
    assert pedal["config"]["active_page"] == 1
    assert pedal["buttons"][10]["cc"] == 99
    pedal.sent()
    pedal.tap(PUSH)
    assert pedal.sent() == [cc(99, 127), cc(99, 0)]


def test_rx_updates_push_state_without_leds(boot):
    pedal = boot(std10(push={"enabled": True, "label": "P", "cc": 70, "mode": "toggle"}))
    leds = pedal.leds()
    pedal["_process_midi_msg"](ControlChange(70, 127, channel=0))
    assert pedal["button_states"][10].state is True
    assert pedal.leds() == leds
    pedal.tap(PUSH)  # next press sends the opposite of what the host reported
    assert pedal.sent() == [cc(70, 0)]


def test_rx_cc_step_value_reaches_push(boot):
    pedal = boot(std10(push={"enabled": True, "label": "P", "type": "cc_inc", "cc": 31}))
    pedal["_process_midi_msg"](ControlChange(31, 60, channel=0))
    pedal["flush_cc_step_updates"]()
    pedal.tap(PUSH)
    assert pedal.sent() == [cc(31, 61)]


def test_non_std10_ignores_encoder_push(boot):
    cfg = {"device": "mini6", "pages": [{
        "buttons": [{"label": str(i + 1), "cc": 20 + i, "color": "white"} for i in range(6)],
        "encoder": {"enabled": True, "cc": 11, "label": "ENC",
                    "push": {"enabled": True, "label": "P", "cc": 14}}}]}
    pedal = boot(cfg)
    assert pedal["BUTTON_SLOTS"] == 6 and len(pedal["buttons"]) == 6
    pedal.tap(0)  # Mini6 switch 0 is footswitch 1
    assert pedal.sent() == [cc(20, 127)]


@pytest.mark.parametrize("path", sorted(FW.glob("config*.json")), ids=lambda p: p.name)
def test_shipped_configs_boot_and_every_switch_works(boot, path):
    """Every shipped config boots and survives a tap and a long hold on every switch."""
    pedal = boot(json.loads(path.read_text()))
    for sw in range(len(pedal["switches"])):
        pedal.tap(sw)
        pedal.clock.t += 0.1
        pedal.hold(sw, 2.0)
        pedal.clock.t += 0.1
    pedal.clock.t += 10
    pedal["update_pc_flash_timers"]()


def test_editor_saved_config_runs_on_the_pedal(boot):
    """End to end: the JSON the editor's Save to File… wrote (fixture, also saved through
    Rust's write_config_file in config_files.rs) boots, and each page's push works."""
    pedal = boot(json.loads((REPO / "tests" / "fixtures" / "editor-saved-encoder-push.json").read_text()))
    leds = pedal.leds()
    # Page 1: PC 5 push, Also send note 60.
    pedal.tap(PUSH)
    assert pedal.sent() == [(ProgramChange(5), 0), (NoteOn(60, 100), 0)]
    # Page 2: push and footswitch 1 share select group "amps" on CC 60.
    pedal["switch_page"](1)
    states = pedal["button_states"]
    pedal.tap(1)
    pedal.tap(PUSH)
    assert pedal.sent() == [cc(60, 1), cc(60, 2)]
    assert states[10].state and not states[0].state
    # Page 3: keytimes push.
    pedal["switch_page"](2)
    pedal.tap(PUSH)
    pedal.clock.t += 0.1
    pedal.hold(PUSH, 2.0)
    assert pedal.sent() == [cc(41, 1), cc(41, 1), cc(42, 2)]
    pedal["switch_page"](0)
    assert pedal.leds() == leds
