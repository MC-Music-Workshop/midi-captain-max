"""
Boot-time helpers for boot.py: the USB drive label and the editor's
one-shot "keep the drive visible" flag.

Hardware modules are passed in (storage, microcontroller.nvm) so tests can
drive these with plain fakes.
"""

# NVM byte 1 — set to 1 by the config editor, in the same REPL line as
# microcontroller.reset(), when a save changes the drive name. boot.py shows
# the drive for that one boot so the renamed drive comes back without holding
# switch 1. Byte 0 is the boot-in-progress flag (see boot.py).
KEEP_DRIVE_BYTE = 1


def consume_keep_drive_flag(nvm):
    """True if the editor asked to keep the USB drive visible for this boot.

    Clears the flag, so it applies to exactly one boot. Only writes when the
    flag is set: each NVM write erases a flash sector.
    """
    try:
        if nvm[KEEP_DRIVE_BYTE] == 1:
            nvm[KEEP_DRIVE_BYTE] = 0
            return True
    except Exception as e:
        print(f"⚠️  Keep-drive flag read failed: {e}")
    return False


def apply_drive_label(storage, name):
    """Write `name` to the FAT volume label if it differs. Returns True if written.

    `name` None means the label isn't configured: leave it alone. The label
    lives in the filesystem, so it survives resets and power cycles and a
    normal boot (label already matches) never writes flash.

    CircuitPython can only write the filesystem while the USB host can't, so
    this remounts read-write, sets the label, and always remounts read-only
    again (host writable) — a failure must never leave the editor unable to
    save. Never raises.
    """
    if name is None:
        return False
    try:
        mount = storage.getmount("/")
        if mount.label == name:
            return False
        storage.remount("/", readonly=False)
        try:
            mount.label = name
        finally:
            storage.remount("/", readonly=True)
        return True
    except Exception as e:
        print(f"⚠️  Drive label warning: {e}")
        return False
