"""
Pages RAM Probe -- measure cost of single-file multi-page config on-device.

Decides single-file vs per-page storage for issue #15 (Pages). We chose
single-file (one /config.json holding a `pages` array); this probe measures
whether realistic page counts fit in RP2040 RAM before the design lands.

What it does:
- Loads the real /config.json as a representative page (page-level fields only;
  device-level keys are lifted above the pages array in the single-file shape).
- Synthesizes an N-page config text {<device-level>,"pages":[page,...]} and
  parses it with json, the same structure the runtime would hold resident.
- Reports retained heap and per-page cost at N = 5 / 15 / 30, then projects
  to 50 and 99 pages.

Deploy (std10):
  cp firmware/dev/experiments/pages_ram_probe.py /Volumes/CIRCUITPY/code.py
  cp firmware/dev/config.json                    /Volumes/CIRCUITPY/config.json
Eject, power-cycle, then open serial:
  screen /dev/tty.usbmodem* 115200

Reading the result:
  `retained` is the steady-state heap the parsed config occupies -- the number
  that actually decides viability. This probe runs on a near-empty heap, so
  `free-left` OVERSTATES real headroom. Compare `retained` against free RAM in
  the FULL firmware after boot (print gc.mem_free() at the end of code.py init).
  Single-file is viable if retained << that figure with comfortable margin.
"""

import gc
import time
import json  # CircuitPython ships `json` (load/loads/dump/dumps)

PAGE_COUNTS = (5, 15, 30)
TEMPLATE = "/config.json"
# Keys that live at the top level (above `pages`), not per page.
DEVICE_KEYS = ("device", "usb_drive_name", "dev_mode")


def free():
    gc.collect()
    return gc.mem_free()


# Load the real config; split into device-level vs page-level bodies.
with open(TEMPLATE) as f:
    base = json.load(f)

device_level = {k: base[k] for k in DEVICE_KEYS if k in base}
page = {k: v for k, v in base.items() if k not in DEVICE_KEYS}

# Serialize once so building N-page text is cheap (refs to one string).
page_text = json.dumps(page)
dev_inner = json.dumps(device_level)[1:-1]  # drop outer braces -> "k":v,"k":v

print("=" * 50)
print("Pages RAM Probe (single-file)")
print("=" * 50)
print("free at start:        %d bytes" % free())
print("one page serialized:  %d bytes" % len(page_text))
print()
print("N    text     retained   per-page   free-left")
print("-" * 50)

per_page = []
for n in PAGE_COUNTS:
    pages_text = "{%s,\"pages\":[%s]}" % (dev_inner, ",".join([page_text] * n))
    gc.collect()
    before = gc.mem_free()
    cfg = json.loads(pages_text)
    after = free()
    retained = before - after  # page_text/pages_text alive in both -> nets to dict
    if len(cfg["pages"]) != n:
        raise ValueError("page count mismatch: %d != %d" % (len(cfg["pages"]), n))
    per = retained / n
    per_page.append(per)
    print("%-3d  %6dB  %7dB  %6.0fB  %8dB" % (n, len(pages_text), retained, per, after))
    cfg = None
    pages_text = None
    gc.collect()

avg = sum(per_page) / len(per_page)
print("-" * 50)
print("avg retained / page:  %.0f bytes" % avg)
print("projected 50 pages:   %.0f bytes" % (avg * 50))
print("projected 99 pages:   %.0f bytes" % (avg * 99))
print()
print("Compare `retained` against free RAM in the FULL firmware after boot,")
print("not against this probe's free-left (heap here is near-empty).")

while True:
    time.sleep(1)
