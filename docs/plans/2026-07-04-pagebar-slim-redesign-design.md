# PageBar slim redesign: ◀▶ navigate, page management moves to a modal

**Issue:** #15 (pages, P4a follow-up) · **Status:** approved · **Date:** 2026-07-04

## Problem

During P4a manual smoke testing, the tester used the PageBar's `◀ ▶` buttons
expecting *previous/next page* navigation. They are actually *reorder*
buttons: they move the current page's position, and the selection follows the
moved page — so the picker number changes while the form content stays the
same. Combined with duplicated (identical) pages, this read as "page
switching is broken / edits stick across pages" and cost a full debugging
session. Arrow buttons next to a page picker will be read as navigation by
most users; the affordance is wrong, not the user.

## Design

### The bar: navigation only

```text
Page [ 2: Solo ▼ ]  ◀  ▶   [Edit Pages…]
```

- `◀ ▶` are **previous/next page** navigation. Disabled at the first/last
  page (no wrap-around). Same commit-pending-edit guard as the dropdown.
- The dropdown is unchanged — direct jump to any page.
- `Edit Pages…` opens the management modal. Verb-labeled so its scope is
  obvious relative to the arrows.
- The bar's Add / Duplicate / Rename / Delete buttons and the inline-rename
  mode are removed (with the `renaming` state juggling).

### The modal: macOS list-editing paradigm

```text
┌ Edit Pages ────────────────────┐
│  1  Intro                      │
│  2  Solo             ← selected│
│  3  Outro                      │
│                                │
│  [+] [−] [Duplicate]  [↑] [↓]  │
│                        [Done]  │
└────────────────────────────────┘
```

- Vertical list of pages; clicking a row selects it **and makes it the
  active page** (the form behind the modal follows). Selection = active page,
  always — so every operation targets the active page and the existing store
  helpers apply unchanged.
- `+` adds a device-sized page (existing `addPage`), `−` deletes the selected
  page (existing `deletePage`, disabled at 1 page), `Duplicate` copies
  (existing `duplicatePage`), `↑ ↓` reorder (existing `movePage`, selection
  follows the moved page).
- **Rename:** double-click a row to edit its name inline. Enter commits
  (existing `updatePageField('name', …)`), Escape cancels, `maxlength` 24.
- Every operation remains one undo step — no store changes at all; this is a
  presentation-layer reshuffle.
- Close via `Done`, Escape, or backdrop click. Escape cancels an in-progress
  rename first, then closes on the next press.
- Opening the modal runs the commit-pending-edit guard once (clicking the
  `Edit Pages…` button does not blur a focused form field in WebKit).

## Testing

- Update existing e2e specs that used the removed bar buttons (`Add`,
  `Duplicate`, `Delete`) to go through the modal.
- New e2e coverage: `◀ ▶` navigate and disable at the ends; modal reorder,
  add, delete, duplicate, rename; in-flight-edit guard on `◀ ▶`.
- Store unit tests are untouched (no store changes).
