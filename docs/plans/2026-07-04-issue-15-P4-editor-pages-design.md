# Issue #15 P4 — Editor Pages UI (Design / Spec)

> **For Claude:** This is a SPEC, not an executable plan. Each sub-phase below gets its
> own P2-style runnable plan (bite-sized TDD tasks) written *after* the decision gates
> are resolved. REQUIRED SUB-SKILL for those plans: `writing-plans`; for execution:
> `executing-plans`.

**Date:** 2026-07-04
**Branch:** spec authored on `15-pages-p3b`; P4 work branches off `main` after P3b merges.
**Phase:** P4. Follows P1 (schema+migration), P2 (runtime `switch_page()`), P3 (button
triggers), P3b (MIDI-IN CC `page_control`).

**Goal:** Make pages first-class in the GUI editor — select, create, copy, rename,
delete, reorder; edit the per-page fields the firmware already honors; expose the
`page_control` and button page-trigger fields shipped in P3/P3b; page templates.

**Architecture:** All work rides the existing `active_page` seam in
`config-editor/src/lib/formStore.ts` — the editor already renders exactly one page
(`activePage()`, `pageScopedPath()`, `currentPage`). P4 adds page mutation helpers to
the store, a page bar UI, an explicit per-page field-update path (`updatePageField`),
all-pages validation, and template import/export via new Tauri commands. One firmware
touch: font reload in `switch_page()` for the per-page `display` override (P4c).

**Tech stack:** Svelte 5 + Tauri 2 (editor), Rust `config.rs`/`commands.rs`
(validation + IO), CircuitPython `core/config.py` + `code.py` (P4c only), JSON Schema
→ `types.generated.ts` (#81 three-layer tax where schema changes — P4 adds **no new
schema fields**; everything below already exists in the schema).

---

## What exists today (verified 2026-07-04)

| Piece | State | Where |
|---|---|---|
| Page seam | Editor renders `pages[active_page]` only; `PAGE_SCOPED_PATH` regex routes `buttons/encoder/expression` writes into the active page | `formStore.ts:34-53` |
| `active_page` setter | **None.** No page CRUD helpers either (no add/remove/duplicate/reorder) | `formStore.ts` (comment at `:29-32` anticipates P4) |
| Save flow | Validate → `normalizeConfig` → `writeConfigRaw(device.config_path)` → optional restart (#48). No path picker; `validate_device_path` (Rust) restricts writes to device volumes | `+page.svelte:199-237`, `commands.rs:142-190` |
| Client validation | Active page **only**; error keys deliberately unprefixed to match component lookups | `validation.ts:100-114` |
| Rust validation | Loops **all** pages with `Page N, ` prefixes; pages 1–20; no `page_step`/`page` checks; no per-page `global_channel`/`Page.name` checks | `config.rs:531-769` |
| Page-switch button types | Type + mode dropdowns render; `page_step`/`page` fields **JSON-only** (no inputs, no validation in either layer) | `ButtonRow.svelte:299-411`, `validation.ts:175-217`, `config.rs:588-633` |
| `page_control` (P3b) | Schema + Rust structs + firmware shipped; **no editor widget** | `config.rs:427-458`, firmware `AGENTS.md:244` |
| Per-page `display`/`global_channel` | In schema since P1, "carried but inert" in editor; `normalizeConfig` already strips empty per-page `display`; firmware resolves per-page `global_channel` (P2) but **not** per-page `display` | `formStore.ts:645-648`, `config.rs:464-477` |
| Templates / save-as | Nothing. Capabilities grant `dialog:default` only — no fs or dialog save/open scope | `capabilities/default.json:6-10` |
| Dialog/prompt idioms | Tauri `ask()`/`message()` for confirms; **no text-input prompt** component (needed for rename) | `+page.svelte:4,100,223` |
| CRUD idiom to copy | Keytimes add/remove rows + `__uiId`-keyed `{#each}` | `KeytimesEditor.svelte:94-156`, `formStore.ts:310-368` |

## Requirements traced to issue #15

- "Pages supported in GUI as tabs or drop-down" → P4a.
- "Pages can be copied, renamed, deleted" (+ session file adds **reordered**) → P4a.
- "Saved as templates" → P4d.
- "Save each page in a common folder or anywhere else; common folder default" → **reinterpreted** (see P4d): the P0 storage decision locked single-file `config.json` with a `pages[]` array, so per-page save files don't exist. The surviving intent is *templates*: export a page to a JSON file (common templates folder by default, anywhere via save dialog) and import it back into any config.
- "Changes must be saved before application to the device" → already satisfied by the #48 flow (validate → write → opt-in restart); no P4 work beyond keeping the dirty flag honest across page CRUD.

---

## Decisions

### Locked (user-confirmed 2026-07-04, walked through one-by-one; all as recommended)

| # | Decision | Recommendation | Rationale |
|---|---|---|---|
| D1 | Selector UI: tabs vs dropdown | **Dropdown page bar** (page `<select>` + Add / Duplicate / Rename / Delete buttons, ◀▶ or drag for reorder), placed inside `ConfigForm` directly above `ButtonsSection` | 20-page cap makes tabs wrap badly; a `<select>` matches the existing header device-selector idiom; the bar sits above exactly the sections that are page-scoped (Buttons/Encoder/Expression), signalling scope. Device-wide sections (Device, Display*, MIDI Thru, Firmware) stay above/below unchanged. |
| D2 | Does the page selector set `active_page`? | **LOCKED (user, 2026-07-04): Yes — selector writes `active_page` directly; device boots into the last-saved page** (the page selected in the editor at save time) | One source of truth; the whole seam (`activePage()`, `pageScopedPath()`, validation, `currentPage`) is already keyed on `config.active_page`, and the P1 code comment anticipated exactly this. Boot-into-last-saved-page is the intended behavior, not a tolerated side effect. Door open for a later separate "boot page" control — do not build it now (YAGNI). |
| D3 | Delete last page | **Forbidden** (Delete disabled at 1 page) | Rust `validate()` rejects 0 pages; editor must never produce an unsaveable config. |
| D4 | Rename UX | Inline text input in the page bar (edit-in-place), writing `pages[i].name` | No prompt-dialog component exists; inline edit avoids building one. `name` ≤24 chars (schema), validated client-side + Rust (closes part of review item #8). |
| D5 | Multi-page client validation (review item #6) | **Two channels:** inline error Map stays active-page-only and unprefixed (zero component churn); on **save**, loop all pages and surface non-active-page failures as save-blocking summary lines ("Page 2: buttons[3]: CC out of range") in the existing footer `stores.ts` string[] (currently never populated) | Fixes the real bug (bad button on a non-active page currently passes client check and dies as an opaque Rust save error) without breaking the unprefixed-error-key convention that components depend on. |
| D6 | Per-page field routing (review item #5) | **New explicit `updatePageField(path, value)`** that always prefixes `pages[activePageIndex]`; new per-page UI (name, display override, future global_channel) uses it. `PAGE_SCOPED_PATH` regex + `updateField` stay untouched for the existing buttons/encoder/expression components | `global_channel` and `display` exist at BOTH levels, so name-based regex routing is inherently ambiguous for them — the allow-list can never be safely generalized. Explicit beats clever; zero churn in existing components. |
| D7 | Template scope | **Page templates only** (single page object per file), not whole-config templates | Whole-config save/load already exists (it's the config file itself). The issue's per-page-file intent maps to page granularity. |
| D8 | Template location + IO | New Rust commands `export_page_template` / `import_page_template` / `list_page_templates`; default folder = Tauri `appDataDir()/templates` (created on demand); "anywhere else" via the dialog plugin's save/open file pickers. Device-write restriction (`validate_device_path`) does **not** apply to template IO — templates are host-side files | Keeps the security posture: device volumes stay locked to config writes; templates get their own commands with their own (shape-validating) checks instead of loosening `validate_device_path`. Needs `dialog` save/open capability added to `capabilities/default.json`. |
| D9 | Imported-template shape drift | Import validates the page against the **current device** (button count, capabilities) using the existing Rust page checks; on mismatch, reject with the validation message — no silent reshaping | Same fail-loud posture as `validate()`; `setDevice`-style reshaping of foreign data would silently discard buttons. |
| D10 | Per-page display firmware behavior (P4c) | `switch_page()` re-resolves effective display (page override → device) and, only when the effective font size *changes*, reloads label fonts **in place** (update existing `label.font`, never recreate label objects) | Matches the P2 in-place-update rule (RP2040 RAM fragmentation). Deferral reason was font-reload RAM churn — so P4c starts with a mandatory RAM probe step (see risks). |

### Locked by prior phases (do not reopen)

- Single-file `pages[]` storage; 20-page cap (P0).
- Reset-on-entry page state; PC memory carries across (P2).
- `page_control` schema/precedence/sanitize semantics (P3b).
- Unprefixed client error keys for active-page inline errors (P1, reaffirmed by D5).

---

## Sub-phases

Each is independently shippable, in this order. P4b has no dependency on P4a and can
run first/parallel if convenient; P4c and P4d depend on P4a's store helpers.

### P4a — Page CRUD + selector + all-pages validation (the core)

**Store (`formStore.ts`):** add and export
- `setActivePage(i)` — clamp, write `config.active_page`, push history. NOT dirty-only-UI: per D2 this is a real config field change (dirty = true).
- `addPage()` — append `{buttons: [...device-sized defaults]}` (reuse the `setDevice` sizing tables at `:447-480`), switch to it.
- `duplicatePage(i)` — deep-clone (strip + re-attach `__uiId`s via `_attachUiIds` pattern), insert after `i`, switch to it. Enforce 20-page cap (disable button at cap).
- `deletePage(i)` — forbidden at 1 page (D3); re-clamp `active_page`.
- `movePage(i, j)` — reorder; keep `active_page` pointing at the same page object.
- All: single history checkpoint each (undo/redo works page-wise for free).

**UI:** new `PageBar.svelte` (select + buttons + inline rename per D4), slotted in
`+page.svelte:380-390` between `DeviceSection`/`MidiThruSection`-group and
`ButtonsSection` (exact section ordering finalized in the runnable plan). Keyed by a
page-level `__uiId` (extend `_attachUiIds` to stamp pages, same idiom as
`KeytimesEditor.svelte:103`).

**Validation:**
- Client (D5): extract the per-page body of `validateConfig()` into
  `validatePage(page, device)`; save path loops all pages, active page keeps the
  inline Map, others produce prefixed summary strings into the footer list. Save
  blocked on any page failing.
- `pages[i].name` ≤24 chars: client + Rust `validate()` (Rust currently checks it
  nowhere — closes the `Page.name` half of review item #8).

**Tests:** Vitest/store tests for each CRUD helper (cap, clamp, reorder-follows-active,
dirty flag, undo); validation tests for a bad button on a non-active page blocking
save; Rust test for over-long `Page.name`; `svelte-check`; full `./tools/test-all.sh`.

### P4b — Form widgets for shipped firmware features (no schema changes)

1. **Button `page_step`/`page` inputs** (`ButtonRow.svelte:299-411`): add the missing
   type-specific branches — `page_inc`/`page_dec` get a `page_step` number input
   (≥1); `page_jump` gets a 0-based `page` index input with a hint showing the page
   name. Client validation branches in `validation.ts` + Rust `validate()` checks
   (`page_step ≥ 1`; `page` within `0..pages.len()` — cross-field, mirrors the
   firmware clamp but fails loud in the editor per the P1 asymmetry rule).
2. **`page_control` section**: new device-wide `PageControlSection.svelte` (Accordion
   idiom): `enabled` checkbox, `channel` (empty = any), three fixed rows jump/inc/dec
   with cc / value / page_step inputs matching the P3b 3-slot shape ("clean editor UI
   later (3 rows, no list management)" — that promise lands here). Device-wide paths →
   plain `updateField`, no seam work. Client validation mirroring the Rust ranges
   (cc 0–127, channel 0–15, value 0–127, page_step ≥1); Rust already validates
   (`config.rs:720-762`).

**Tests:** validation unit tests both layers; store/component tests for the new
inputs; `test-all.sh`.

### P4c — Per-page overrides (editor + firmware)

1. **Editor:** `DisplaySection.svelte` gains an "Override for this page" toggle;
   when on, the three selects write via `updatePageField('display.<field>', v)` (D6);
   when toggled off, clear `pages[i].display` (normalizeConfig already strips empties,
   `formStore.ts:645-648`). Optionally same pattern for per-page `global_channel`
   (schema field exists; firmware already resolves it — P2). Rust `validate()` gains
   the per-page `global_channel` 0–15 check (closes the rest of review item #8).
2. **Firmware:** `switch_page()` font reload per D10. Pure resolution helper
   (`effective_display(cfg)` or similar) in `core/config.py` with pytest coverage;
   the reload wiring in `code.py` tested on-device via REPL (same split as P2).

**Gate before building:** RAM probe on RP2040 — load both font sizes' worth of glyphs
across repeated switches, watch the dev_mode RAM low-water line. If fragmentation is
unacceptable, fallback options (pre-load all font sizes at boot; or restrict override
to non-font display fields) get decided then, not now.

### P4d — Page templates

- Rust: `export_page_template(path, page_json)` / `import_page_template(path) -> Value`
  / `list_page_templates() -> Vec<...>` per D7–D9, with shape validation on import
  against the current device. Register in `lib.rs:18-34`; add dialog save/open
  capability to `capabilities/default.json`.
- UI: "Save page as template…" + "Add page from template…" in the PageBar overflow;
  default to the common templates folder (`appDataDir()/templates`), file pickers for
  elsewhere.
- Tests: Rust round-trip + reject-on-device-mismatch; store test for insert-at-cap.

### P4-cleanup (ride along with whichever sub-phase touches the area)

- Drop the dead typed `read_config`/`write_config` path (frontend uses only the
  `*_raw` commands — P1 finding; "drop legacy write path" in the session file).
  Verify nothing else calls them before removing.
- Python `validate_config` guard/warn for empty `pages: []` (P1 review item #3;
  `get_active_page` already never crashes on it — this is belt-and-braces parity
  with the Rust 1–20 bound).

---

## Explicitly out of scope (unchanged from prior phases)

- `pc_carryover` toggle — future, unrequested; one-line seam documented in P2 design.
- Per-page state preservation ("remember" latches/cycles) — future.
- Serial/network page-switch command — issue marks it very low priority.
- P5: docs, VS Code `json.schemas` wiring, multi-page example config, RAM ceiling
  documentation — separate phase after P4.
- OEM 99-page count parity — impossible single-file on RP2040 (~88 KB budget, see
  RAM probe evidence); cap stays 20.

## Risks / open verifications

- **Font-reload RAM churn (P4c)** — the original deferral reason. Mitigation: probe
  first (gate above); in-place `.font` swap only; never recreate labels.
- ~~**P3b hardware check still pending**~~ **RESOLVED (hardware-verified
  2026-07-05, during P4b smoke):** `CC20 val 1` → page 2, `CC20 val 0` → page 1 —
  jump values are 0-based as designed. No firmware or editor-hint change needed.
- **Capabilities widening (P4d)** — adding dialog save/open scope is deliberate and
  minimal; do NOT grant blanket `fs:*`; template IO goes through the new commands.
- **`setDevice` two-step-shrink tail loss** (pre-existing, noted in P1 review) — page
  CRUD multiplies exposure slightly (per-page stashes already exist,
  `formStore.ts:512-534`); not a P4 deliverable, but P4a tests must not regress it.

## Execution handoff

All gates D1–D10 are LOCKED (user-confirmed 2026-07-04). No open decisions remain.
Next: write one P2-style runnable plan per sub-phase (`writing-plans` →
`executing-plans`, separate sessions per repo convention). P4a first. The only
mid-flight gate left is the P4c RAM probe result (D10 fallback choice happens then).
