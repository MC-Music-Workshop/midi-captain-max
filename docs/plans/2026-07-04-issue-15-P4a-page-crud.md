# Issue #15 P4a — Page CRUD + Selector + All-Pages Validation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make pages first-class in the GUI editor: a page bar (select, add, duplicate, rename, delete, reorder) backed by store CRUD helpers, plus save-blocking validation of all pages (not just the active one).

**Architecture:** All work rides the existing `active_page` seam in `config-editor/src/lib/formStore.ts` — the editor already renders exactly one page. P4a adds store mutation helpers (each a single undo checkpoint), a new `PageBar.svelte` above `ButtonsSection`, an explicit `updatePageField()` write path (design decision D6), a `validatePage()` extraction with all-pages save summary (D5), and a Rust `Page.name` length check. No schema changes — every field already exists.

**Tech Stack:** Svelte 5 (runes) + Tauri 2, TypeScript, Vitest (added by Task 1), Rust (`config.rs`), existing test harness `./tools/test-all.sh`.

**Design doc:** `docs/plans/2026-07-04-issue-15-P4-editor-pages-design.md` — decisions D1–D6 govern this plan. Do not re-litigate them.

**Branch:** `15-pages-p4` (this worktree). Commit after every task.

---

## Preflight (no commit)

Fresh-worktree gotcha (see `config-editor/AGENTS.md`): `cargo test` fails until firmware resources are staged.

```bash
./tools/bundle-firmware-for-dev.sh          # idempotent; stages firmware + CP .uf2
cd config-editor && npm install --no-audit --no-fund && cd ..
```

Sanity: `(cd config-editor/src-tauri && cargo test)` should pass before you start.

---

### Task 1: Add Vitest to config-editor

The editor has **no frontend test runner** (only `svelte-check`). The P4 spec mandates store tests, so Vitest comes in first. This dependency is sanctioned by the user-approved design doc ("Vitest/store tests for each CRUD helper").

**Files:**
- Modify: `config-editor/package.json` (scripts + devDependencies)

**Step 1: Install vitest**

```bash
cd config-editor && npm install -D vitest
```

**Step 2: Add the test script**

In `config-editor/package.json` `"scripts"`, after the `"check:watch"` line, add:

```json
    "test": "vitest run",
```

**Step 3: Verify the runner works**

```bash
cd config-editor && npx vitest run --passWithNoTests
```

Expected: "No test files found" and exit code 0. (Plain `npm test` exits 1 until Task 2 adds the first test file — that's expected.)

**Step 4: Commit**

```bash
git add config-editor/package.json config-editor/package-lock.json
git commit -m "Add Vitest test runner to config-editor (npm test) (#15 P4a)"
```

---

### Task 2: Page-level `__uiId` + first store tests + test-all.sh wiring

Pages need stable identity for the PageBar `{#each}` key (same idiom as keytimes entries, `formStore.ts:96-125`). `_stripUiIds` is already generic — it will strip page-level ids with no changes.

**Files:**
- Modify: `config-editor/src/lib/types.ts:12-20` (Page re-export)
- Modify: `config-editor/src/lib/formStore.ts:104-125` (`_attachUiIds`)
- Create: `config-editor/src/lib/formStore.test.ts`
- Modify: `tools/test-all.sh` (new step)

**Step 1: Write the failing test**

Create `config-editor/src/lib/formStore.test.ts`:

```ts
import { describe, it, expect } from 'vitest';
import { get } from 'svelte/store';
import { formState, loadConfig, normalizeConfig } from './formStore';
import type { MidiCaptainConfig, DeviceType, Page } from './types';

// Minimal valid config: one1 = 1 button per page, so validation stays green.
export function makeConfig(pageCount = 2, device: DeviceType = 'one1'): MidiCaptainConfig {
  const pages = Array.from({ length: pageCount }, (_, i) => ({
    name: `P${i}`,
    buttons: [{ label: `B${i}`, cc: 20 + i }],
  }));
  return { device, active_page: 0, pages };
}

describe('page __uiId stamping', () => {
  it('loadConfig stamps a distinct __uiId on every page', () => {
    loadConfig(makeConfig(2));
    const pages = get(formState).config.pages as Page[];
    expect(typeof pages[0].__uiId).toBe('number');
    expect(typeof pages[1].__uiId).toBe('number');
    expect(pages[0].__uiId).not.toBe(pages[1].__uiId);
  });

  it('normalizeConfig strips page __uiIds from save output', () => {
    loadConfig(makeConfig(1));
    const out = normalizeConfig(get(formState).config);
    expect('__uiId' in out.pages[0]).toBe(false);
  });
});
```

**Step 2: Run it to verify it fails**

```bash
cd config-editor && npx vitest run src/lib/formStore.test.ts
```

Expected: FAIL — first test: `expected 'undefined' to be 'number'` (second test passes already because `_stripUiIds` is generic — fine, it locks the behavior in).

**Step 3: Extend the `Page` type**

In `config-editor/src/lib/types.ts`, remove `Page` from the re-export list (lines 12-20) and add an extended alias below the `KeytimesMessage` line (line 26):

```ts
export type {
  StateOverride,
  EncoderConfig,
  EncoderPush,
  ExpressionConfig,
  ExpressionPedals,
  DisplayConfig,
} from './types.generated';
```

```ts
// Pages carry the same optional ephemeral `__uiId` as keytimes entries so the
// PageBar {#each} keys by stable identity across structuredClone edits.
// Stripped by normalizeConfig before write — never reaches disk.
export type Page = import('./types.generated').Page & { __uiId?: number };
```

**Step 4: Stamp pages in `_attachUiIds`**

In `config-editor/src/lib/formStore.ts`, at the top of the `for (const page of cfg.pages ?? [])` loop body in `_attachUiIds` (line 107), add:

```ts
    if (typeof page.__uiId !== 'number') page.__uiId = _nextUiId();
```

(No cast needed — `formStore.ts` already imports `Page` from `./types`, which is now the extended type, and `cfg.pages` elements resolve to it via `MidiCaptainConfig`... **verify with svelte-check in Step 6**; if the generated `MIDICaptainConfig.pages` element type doesn't pick up the alias, write `(page as Page).__uiId` instead.)

**Step 5: Run tests to verify they pass**

```bash
cd config-editor && npx vitest run src/lib/formStore.test.ts
```

Expected: 2 PASS.

**Step 6: Type-check**

```bash
cd config-editor && npm run check
```

Expected: 0 errors, 0 warnings.

**Step 7: Wire vitest into test-all.sh**

In `tools/test-all.sh`, after the svelte-check step (the `(cd config-editor && npm run check)` line) and before the `step "generate:types (schema → TS)"` line, add:

```bash
step "vitest (frontend stores)"
(cd config-editor && npm test)
```

Run `./tools/test-all.sh` once here to confirm the new step slots in green.

**Step 8: Commit**

```bash
git add config-editor/src/lib/types.ts config-editor/src/lib/formStore.ts config-editor/src/lib/formStore.test.ts tools/test-all.sh
git commit -m "Stamp page-level __uiId for stable {#each} keys; wire vitest into test-all.sh (#15 P4a)"
```

---

### Task 3: `setActivePage()` + shared CRUD commit helper

Per D2 the selector writes `config.active_page` directly — a **real config change** (dirty = true), because the device boots into the last-saved page. Each CRUD helper is a single immediate history checkpoint (same pattern as `syncButtonStates`, `formStore.ts:390-420`), so undo/redo works page-wise for free.

**Files:**
- Modify: `config-editor/src/lib/formStore.ts` (new section after `setDevice`, ~line 539)
- Modify: `config-editor/src/lib/formStore.test.ts`

**Step 1: Write the failing tests**

Append to `formStore.test.ts` (extend the existing formStore import with `setActivePage, isDirty, canUndo, undo, currentPage`):

```ts
describe('setActivePage', () => {
  it('switches the rendered page and marks dirty (D2)', () => {
    loadConfig(makeConfig(3));
    setActivePage(2);
    expect(get(formState).config.active_page).toBe(2);
    expect(get(currentPage).name).toBe('P2');
    expect(get(isDirty)).toBe(true);
  });

  it('clamps out-of-range indices', () => {
    loadConfig(makeConfig(3));
    setActivePage(99);
    expect(get(formState).config.active_page).toBe(2);
    setActivePage(-5);
    expect(get(formState).config.active_page).toBe(0);
  });

  it('no-ops when selecting the already-active page', () => {
    loadConfig(makeConfig(2));
    setActivePage(0);
    expect(get(isDirty)).toBe(false);
    expect(get(canUndo)).toBe(false);
  });

  it('is a single undo checkpoint', () => {
    loadConfig(makeConfig(2));
    setActivePage(1);
    expect(get(canUndo)).toBe(true);
    undo();
    expect(get(formState).config.active_page).toBe(0);
  });
});
```

**Step 2: Run to verify failure**

```bash
cd config-editor && npx vitest run src/lib/formStore.test.ts
```

Expected: FAIL — `setActivePage` is not exported.

**Step 3: Implement**

In `formStore.ts`, after the closing brace of `setDevice` (~line 539), add:

```ts
// --- Page CRUD helpers (#15 P4a) ---
//
// Each helper is one immediate history checkpoint (like syncButtonStates), so
// undo/redo steps page-wise. A pending debounced field-edit checkpoint is
// folded into the CRUD checkpoint (its config state is included in the push).
// `mutate` returns false to abort (no state change, no dirty, no history).

export const PAGE_CAP = 20;

function _commitConfigMutation(mutate: (cfg: MidiCaptainConfig) => boolean | void) {
  if (debounceTimer) {
    clearTimeout(debounceTimer);
    debounceTimer = null;
  }
  formState.update(state => {
    const newConfig = structuredClone(state.config);
    if (mutate(newConfig) === false) return state;
    _attachUiIds(newConfig);
    return pushHistory({ ...state, config: newConfig });
  });
  validate();
}

export function setActivePage(index: number) {
  _commitConfigMutation(cfg => {
    const clamped = Math.max(0, Math.min((cfg.pages?.length ?? 1) - 1, index));
    if (clamped === (cfg.active_page ?? 0)) return false;
    cfg.active_page = clamped;
  });
}
```

**Step 4: Run tests to verify they pass**

```bash
cd config-editor && npx vitest run src/lib/formStore.test.ts
```

Expected: all PASS.

**Step 5: Commit**

```bash
git add config-editor/src/lib/formStore.ts config-editor/src/lib/formStore.test.ts
git commit -m "Add setActivePage store helper (#15 P4a): clamp, dirty flag per D2, single undo checkpoint"
```

---

### Task 4: `addPage()`

**Files:**
- Modify: `config-editor/src/lib/formStore.ts`
- Modify: `config-editor/src/lib/formStore.test.ts`

**Step 1: Write the failing tests**

Append (add `addPage` to the import):

```ts
describe('addPage', () => {
  it('appends a device-sized page and switches to it', () => {
    loadConfig(makeConfig(1)); // one1 → 1 button per page
    addPage();
    const cfg = get(formState).config;
    expect(cfg.pages).toHaveLength(2);
    expect(cfg.active_page).toBe(1);
    expect(cfg.pages[1].buttons).toHaveLength(1);
    expect(get(isDirty)).toBe(true);
  });

  it('no-ops at the 20-page cap', () => {
    loadConfig(makeConfig(20));
    addPage();
    expect(get(formState).config.pages).toHaveLength(20);
    expect(get(isDirty)).toBe(false);
  });

  it('is undoable', () => {
    loadConfig(makeConfig(1));
    addPage();
    undo();
    expect(get(formState).config.pages).toHaveLength(1);
  });
});
```

**Step 2: Run to verify failure** (`npx vitest run src/lib/formStore.test.ts` → `addPage` not exported)

**Step 3: Implement**

Below `setActivePage` in `formStore.ts`:

```ts
export function addPage() {
  _commitConfigMutation(cfg => {
    if (cfg.pages.length >= PAGE_CAP) return false;
    // Size the new page to the device (reuse the setDevice sizing table);
    // fall back to the active page's shape if device is somehow unset.
    const count = cfg.device
      ? DEVICE_BUTTON_COUNT[cfg.device]
      : activePage(cfg).buttons.length;
    cfg.pages.push({ buttons: createDefaultButtons(0, count - 1) });
    cfg.active_page = cfg.pages.length - 1;
  });
}
```

(`_attachUiIds` in `_commitConfigMutation` stamps the new page's `__uiId`.)

**Step 4: Run tests to verify they pass**

**Step 5: Commit**

```bash
git add config-editor/src/lib/formStore.ts config-editor/src/lib/formStore.test.ts
git commit -m "Add addPage store helper (#15 P4a): device-sized defaults, 20-page cap"
```

---

### Task 5: `duplicatePage()`

**Files:**
- Modify: `config-editor/src/lib/formStore.ts`
- Modify: `config-editor/src/lib/formStore.test.ts`

**Step 1: Write the failing tests**

Append (add `duplicatePage` to the import):

```ts
describe('duplicatePage', () => {
  it('inserts a deep copy after the source and switches to it', () => {
    loadConfig(makeConfig(2));
    duplicatePage(0);
    const cfg = get(formState).config;
    expect(cfg.pages).toHaveLength(3);
    expect(cfg.pages[1].name).toBe('P0');
    expect(cfg.active_page).toBe(1);
    // Deep copy: editing the duplicate must not touch the source.
    cfg.pages[1].buttons[0].label = 'EDIT';
    expect(cfg.pages[0].buttons[0].label).toBe('B0');
  });

  it('gives the duplicate a fresh __uiId (no shared {#each} keys)', () => {
    loadConfig(makeConfig(1));
    duplicatePage(0);
    const pages = get(formState).config.pages as Page[];
    expect(typeof pages[1].__uiId).toBe('number');
    expect(pages[1].__uiId).not.toBe(pages[0].__uiId);
  });

  it('no-ops at the cap', () => {
    loadConfig(makeConfig(20));
    duplicatePage(0);
    expect(get(formState).config.pages).toHaveLength(20);
    expect(get(isDirty)).toBe(false);
  });
});
```

**Step 2: Run to verify failure**

**Step 3: Implement**

```ts
export function duplicatePage(index: number) {
  _commitConfigMutation(cfg => {
    if (cfg.pages.length >= PAGE_CAP) return false;
    const src = cfg.pages[index];
    if (!src) return false;
    const clone = structuredClone(src);
    // The clone carries the source's __uiIds (page + nested keytimes) — strip
    // them so _attachUiIds stamps a fresh identity for every level.
    _stripUiIds(clone);
    cfg.pages.splice(index + 1, 0, clone);
    cfg.active_page = index + 1;
  });
}
```

**Step 4: Run tests to verify they pass**

**Step 5: Commit**

```bash
git add config-editor/src/lib/formStore.ts config-editor/src/lib/formStore.test.ts
git commit -m "Add duplicatePage store helper (#15 P4a): deep clone, fresh __uiIds, insert after source"
```

---

### Task 6: `deletePage()`

**Files:**
- Modify: `config-editor/src/lib/formStore.ts`
- Modify: `config-editor/src/lib/formStore.test.ts`

**Step 1: Write the failing tests**

Append (add `deletePage` to the import):

```ts
describe('deletePage', () => {
  it('refuses to delete the last page (D3)', () => {
    loadConfig(makeConfig(1));
    deletePage(0);
    expect(get(formState).config.pages).toHaveLength(1);
    expect(get(isDirty)).toBe(false);
  });

  it('re-clamps active_page when deleting the active last page', () => {
    loadConfig(makeConfig(3));
    setActivePage(2);
    deletePage(2);
    const cfg = get(formState).config;
    expect(cfg.pages).toHaveLength(2);
    expect(cfg.active_page).toBe(1);
  });

  it('keeps the active page stable when deleting an earlier page', () => {
    loadConfig(makeConfig(3));
    setActivePage(2);
    deletePage(0);
    expect(get(formState).config.active_page).toBe(1);
    expect(get(currentPage).name).toBe('P2');
  });
});
```

**Step 2: Run to verify failure**

**Step 3: Implement**

```ts
export function deletePage(index: number) {
  _commitConfigMutation(cfg => {
    if (cfg.pages.length <= 1) return false; // D3: never produce an unsaveable config
    if (!cfg.pages[index]) return false;
    cfg.pages.splice(index, 1);
    const ap = cfg.active_page ?? 0;
    cfg.active_page = Math.min(ap > index ? ap - 1 : ap, cfg.pages.length - 1);
  });
}
```

**Step 4: Run tests to verify they pass**

**Step 5: Commit**

```bash
git add config-editor/src/lib/formStore.ts config-editor/src/lib/formStore.test.ts
git commit -m "Add deletePage store helper (#15 P4a): forbidden at 1 page (D3), active_page re-clamp"
```

---

### Task 7: `movePage()`

**Files:**
- Modify: `config-editor/src/lib/formStore.ts`
- Modify: `config-editor/src/lib/formStore.test.ts`

**Step 1: Write the failing tests**

Append (add `movePage` to the import):

```ts
describe('movePage', () => {
  it('reorders pages', () => {
    loadConfig(makeConfig(3));
    movePage(0, 2);
    expect(get(formState).config.pages.map(p => p.name)).toEqual(['P1', 'P2', 'P0']);
  });

  it('active_page follows the moved page', () => {
    loadConfig(makeConfig(3)); // active = 0 (P0)
    movePage(0, 2);
    expect(get(formState).config.active_page).toBe(2);
    expect(get(currentPage).name).toBe('P0');
  });

  it('active_page follows when another page moves across it', () => {
    loadConfig(makeConfig(3));
    setActivePage(1); // P1
    movePage(2, 0);   // P2 jumps to front; P1 shifts right
    expect(get(currentPage).name).toBe('P1');
    expect(get(formState).config.active_page).toBe(2);
  });

  it('no-ops on invalid indices', () => {
    loadConfig(makeConfig(2));
    movePage(0, 5);
    expect(get(isDirty)).toBe(false);
  });
});
```

**Step 2: Run to verify failure**

**Step 3: Implement**

```ts
export function movePage(from: number, to: number) {
  _commitConfigMutation(cfg => {
    const len = cfg.pages.length;
    if (from === to || from < 0 || to < 0 || from >= len || to >= len) return false;
    // Track the active page by object identity so it survives the reorder.
    const activeObj = cfg.pages[activePageIndex(cfg)];
    const [moved] = cfg.pages.splice(from, 1);
    cfg.pages.splice(to, 0, moved);
    cfg.active_page = cfg.pages.indexOf(activeObj);
  });
}
```

**Step 4: Run tests to verify they pass**

**Step 5: Commit**

```bash
git add config-editor/src/lib/formStore.ts config-editor/src/lib/formStore.test.ts
git commit -m "Add movePage store helper (#15 P4a): reorder, active_page follows moved page"
```

---

### Task 8: `updatePageField()` (D6) + empty-name strip

D6: `global_channel` and `display` exist at BOTH config and page level, so name-based regex routing is inherently ambiguous — new per-page UI (rename now, display override in P4c) uses an **explicit** page-prefixed write path. `PAGE_SCOPED_PATH` + `updateField` stay untouched.

**Files:**
- Modify: `config-editor/src/lib/formStore.ts:250-275` (`updateField` refactor) and `:636-658` (`normalizeConfig`)
- Modify: `config-editor/src/lib/formStore.test.ts`

**Step 1: Write the failing tests**

Append (add `updatePageField` to the import):

```ts
describe('updatePageField (D6)', () => {
  it('writes to the active page only', () => {
    loadConfig(makeConfig(2));
    setActivePage(1);
    updatePageField('name', 'Solo');
    const cfg = get(formState).config;
    expect(cfg.pages[1].name).toBe('Solo');
    expect(cfg.pages[0].name).toBe('P0');
    expect(get(isDirty)).toBe(true);
  });
});

describe('normalizeConfig page fields', () => {
  it('strips empty page names from save output', () => {
    loadConfig(makeConfig(1));
    updatePageField('name', '');
    const out = normalizeConfig(get(formState).config);
    expect('name' in out.pages[0]).toBe(false);
  });
});
```

**Step 2: Run to verify failure**

**Step 3: Implement**

Refactor `updateField` (`formStore.ts:250-275`): extract the body into `_updateAtPath`, then both public functions delegate to it. Replace the whole `updateField` function with:

```ts
// Shared write path: set an absolute config path, validate, debounce a history
// checkpoint. updateField routes control-surface paths through the active-page
// regex; updatePageField prefixes explicitly (D6 — see PAGE_SCOPED_PATH note).
function _updateAtPath(absolutePath: string, value: any) {
  if (debounceTimer) {
    clearTimeout(debounceTimer);
  }

  formState.update(state => {
    const newConfig = structuredClone(state.config);
    setNestedValue(newConfig, absolutePath, value);

    return {
      ...state,
      config: newConfig,
      isDirty: true,
    };
  });

  validate();

  debounceTimer = setTimeout(() => {
    formState.update(state => pushHistory(state));
  }, DEBOUNCE_MS);
}

export function updateField(path: string, value: any) {
  const cfg = get(formState).config;
  _updateAtPath(pageScopedPath(cfg, path), value);
}

// Explicit per-page write (D6): always targets the active page, regardless of
// field name. Used by per-page UI (name; display override/global_channel in P4c).
export function updatePageField(path: string, value: any) {
  const cfg = get(formState).config;
  _updateAtPath(`pages[${activePageIndex(cfg)}].${path}`, value);
}
```

In `normalizeConfig` (page map at `:643-648`), after the empty-display strip, add:

```ts
      if (p.name === '') {
        delete p.name;
      }
```

**Step 4: Run tests to verify they pass** (full suite: `npx vitest run` — behavior of `updateField` must be unchanged)

**Step 5: Type-check**

```bash
cd config-editor && npm run check
```

**Step 6: Commit**

```bash
git add config-editor/src/lib/formStore.ts config-editor/src/lib/formStore.test.ts
git commit -m "Add updatePageField explicit per-page write path (D6); strip empty page names on save (#15 P4a)"
```

---

### Task 9: Client validation — extract `validatePage`, add `validateAllPages` + name length (D5)

The real bug D5 fixes: a bad button on a **non-active** page passes the client check today and dies as an opaque Rust save error. Inline error Map stays active-page-only with **unprefixed keys** (locked convention — zero component churn); a new `validateAllPages()` produces prefixed summary strings for the save path.

**Files:**
- Modify: `config-editor/src/lib/validation.ts:100-426`
- Create: `config-editor/src/lib/validation.test.ts`

**Step 1: Write the failing tests**

Create `config-editor/src/lib/validation.test.ts`:

```ts
import { describe, it, expect } from 'vitest';
import { validateConfig, validateAllPages } from './validation';
import type { MidiCaptainConfig } from './types';

function twoPageConfig(): MidiCaptainConfig {
  return {
    device: 'one1',
    active_page: 0,
    pages: [
      { name: 'Home', buttons: [{ label: 'OK', cc: 20 }] },
      { name: 'Bad', buttons: [{ label: 'OK', cc: 200 }] }, // cc out of range
    ],
  };
}

describe('multi-page validation (D5)', () => {
  it('inline validateConfig only covers the active page (unprefixed keys)', () => {
    expect(validateConfig(twoPageConfig()).isValid).toBe(true);
  });

  it('validateAllPages reports non-active-page errors as prefixed summary lines', () => {
    const lines = validateAllPages(twoPageConfig());
    expect(lines).toHaveLength(1);
    expect(lines[0]).toContain('Page 2 (Bad)');
    expect(lines[0]).toContain('buttons[0].cc');
  });

  it('validateAllPages skips the active page — inline errors own it', () => {
    const cfg = twoPageConfig();
    cfg.active_page = 1;
    expect(validateAllPages(cfg)).toHaveLength(0);
    expect(validateConfig(cfg).isValid).toBe(false);
  });

  it('rejects page names over 24 chars (schema maxLength)', () => {
    const cfg = twoPageConfig();
    cfg.pages[0].name = 'A'.repeat(25);
    cfg.pages[1].buttons[0].cc = 20;
    const result = validateConfig(cfg);
    expect(result.errors.get('name')).toContain('24');
  });
});
```

**Step 2: Run to verify failure** (`npx vitest run src/lib/validation.test.ts` → `validateAllPages` not exported)

**Step 3: Refactor `validation.ts`**

This is a mechanical extraction. Add `Page` to the type import (line 1):

```ts
import type { MidiCaptainConfig, Page } from './types';
```

Create `validatePage` containing everything in `validateConfig` that reads page data — i.e. move lines 115-420 (device-specific checks, buttons loop, encoder, expression) verbatim into it, replacing every `config.device` with `device`:

```ts
// Validate one page's control-surface data against the device. Keys are
// UNPREFIXED (buttons[i]…, encoder…, expression…) — for the active page they
// feed the inline error Map that components look up by path (locked convention).
export function validatePage(page: Page, device: MidiCaptainConfig['device']): Map<string, string> {
  const errors = new Map<string, string>();
  const buttons = page.buttons ?? [];
  const encoder = page.encoder;
  const expression = page.expression;

  // Page name: editor-facing metadata, schema caps at 24 chars.
  if (page.name !== undefined && page.name.length > 24) {
    errors.set('name', 'Page name must be 24 characters or less');
  }

  // … device-specific validation moved verbatim from validateConfig
  //   (the whole `if (config.device === 'one1') { … } else if … 'std10') { … }`
  //   chain, with config.device → device) …

  // … `buttons.forEach((btn, idx) => { … })` loop moved verbatim …

  // … `if (encoder?.enabled) { … }` block moved verbatim …

  // … expression `for (const [key, exp] of …)` loop moved verbatim …

  return errors;
}
```

Then replace `validateConfig` with this thin composition (device-wide checks + active page), and add `validateAllPages`:

```ts
export function validateConfig(config: MidiCaptainConfig): ValidationResult {
  const errors = new Map<string, string>();

  // Device-wide fields.
  if (config.usb_drive_name) {
    const err = validators.usbDriveName(config.usb_drive_name);
    if (err) errors.set('usb_drive_name', err);
  }

  // The editor renders the active page; its errors stay unprefixed so they
  // match the paths components use for both updateField and error lookups.
  const pages = config.pages ?? [];
  const apIdx = pages.length
    ? Math.max(0, Math.min(pages.length - 1, config.active_page ?? 0))
    : 0;
  const page = pages[apIdx] ?? { buttons: [] };
  for (const [key, msg] of validatePage(page, config.device)) {
    errors.set(key, msg);
  }

  return {
    isValid: errors.size === 0,
    errors,
  };
}

// D5 save-path check: every NON-active page, as human-readable summary lines
// for the footer error list ("Page 2 (Bad): buttons[0].cc: CC must be…").
// The active page is skipped — its errors surface inline via validateConfig.
export function validateAllPages(config: MidiCaptainConfig): string[] {
  const lines: string[] = [];
  const pages = config.pages ?? [];
  const apIdx = pages.length
    ? Math.max(0, Math.min(pages.length - 1, config.active_page ?? 0))
    : 0;
  pages.forEach((page, i) => {
    if (i === apIdx) return;
    for (const [key, msg] of validatePage(page, config.device)) {
      const label = page.name ? `Page ${i + 1} (${page.name})` : `Page ${i + 1}`;
      lines.push(`${label}: ${key}: ${msg}`);
    }
  });
  return lines;
}
```

**Step 4: Run tests to verify they pass**

```bash
cd config-editor && npx vitest run
```

Expected: validation tests PASS **and** all formStore tests still PASS (the extraction must not change active-page behavior).

**Step 5: Type-check** (`npm run check` → 0 errors/warnings)

**Step 6: Commit**

```bash
git add config-editor/src/lib/validation.ts config-editor/src/lib/validation.test.ts
git commit -m "Extract validatePage; add validateAllPages summary + page-name length check (D5, #15 P4a)"
```

---

### Task 10: Save flow blocks on any page failing

Wire `validateAllPages` into `saveToDevice` and surface the lines in the existing footer error list (`stores.ts` `validationErrors: string[]` — currently never populated; the footer render at `+page.svelte:402-411` already exists).

**Files:**
- Modify: `config-editor/src/routes/+page.svelte:199-210` (`saveToDevice`)

**Step 1: Implement**

In `+page.svelte`, add `validateAllPages` to the formStore-adjacent imports (line 25 area):

```ts
  import { validateAllPages } from '$lib/validation';
```

Replace the top of `saveToDevice` (lines 199-209) with:

```ts
  async function saveToDevice() {
    if (!$selectedDevice) return;

    const isValid = validate();
    // D5: all pages must pass, not just the rendered one. Non-active-page
    // failures land in the footer error list as prefixed summary lines.
    const pageErrors = validateAllPages(get(config));
    $validationErrors = pageErrors;
    if (!isValid || pageErrors.length > 0) {
      await message('Please fix validation errors before saving', {
        title: 'Validation Error',
        kind: 'error'
      });
      return;
    }
```

(The rest of the function is unchanged. On a successful save, `$validationErrors = pageErrors` has already cleared the list to `[]`.)

**Step 2: Type-check**

```bash
cd config-editor && npm run check
```

Expected: 0 errors, 0 warnings.

**Step 3: Run all frontend tests** (`npx vitest run` → all PASS)

**Step 4: Commit**

```bash
git add config-editor/src/routes/+page.svelte
git commit -m "Block save on non-active-page validation failures; surface summary in footer list (D5, #15 P4a)"
```

---

### Task 11: Rust `validate()` — reject `Page.name` over 24 chars

Closes the `Page.name` half of the P3b review item #8: Rust currently checks the name nowhere. The check goes inside the existing per-page loop so errors get the `Page N, ` prefix.

**Files:**
- Modify: `config-editor/src-tauri/src/config.rs:576-586` (page loop) and tests module (`:826+`)

**Step 1: Write the failing test**

In `config-editor/src-tauri/src/config.rs` `mod tests`, add:

```rust
#[test]
fn test_validate_rejects_long_page_name() {
    // 25 chars — one over the schema's maxLength of 24.
    let json = r#"{
        "device": "one1",
        "pages": [{
            "name": "ABCDEFGHIJKLMNOPQRSTUVWXY",
            "buttons": [{"label": "B1", "cc": 20, "color": "green"}]
        }],
        "active_page": 0
    }"#;

    let config = parse_migrated(json);
    let errors = config.validate().unwrap_err();
    assert!(
        errors.iter().any(|e| e.contains("Page 1") && e.contains("exceeds 24 chars")),
        "expected page-name error, got: {errors:?}"
    );
}
```

**Step 2: Run to verify failure**

```bash
cd config-editor/src-tauri && cargo test test_validate_rejects_long_page_name
```

Expected: FAIL — `validate()` returns `Ok(())`, `unwrap_err` panics.

**Step 3: Implement**

In `validate()`'s page loop, directly after the `let pfx = format!("Page {}, ", p + 1);` line (`config.rs:578`), add:

```rust
            // Page name: editor-facing metadata; schema caps it at 24 chars.
            // chars().count() matches JSON Schema maxLength (code points, not bytes).
            if let Some(ref name) = page.name {
                if name.chars().count() > 24 {
                    errors.push(format!("{}page name '{}' exceeds 24 chars", pfx, name));
                }
            }
```

**Step 4: Run tests to verify they pass**

```bash
cd config-editor/src-tauri && cargo test
```

Expected: full suite PASS (run the whole crate, not just the new test).

**Step 5: Commit**

```bash
git add config-editor/src-tauri/src/config.rs
git commit -m "Rust validate(): reject Page.name over 24 chars (#15 P4a, review item 8)"
```

---

### Task 12: `PageBar.svelte` + wiring

D1: dropdown page bar (select + Add / Duplicate / Rename / Delete, ◀▶ reorder) placed directly above `ButtonsSection` — it scopes exactly the page-scoped sections below it. D4: rename is an inline text input (no prompt-dialog component exists; don't build one). No delete confirmation: deletes are one undo away (⌘Z), matching the rest of the editor.

Accessibility bar (repo convention: **0 svelte-check warnings**): label/`for` pairing, `aria-label` on icon buttons, Svelte 5 event syntax (`onclick`, never `on:click`).

**Files:**
- Create: `config-editor/src/lib/components/PageBar.svelte`
- Modify: `config-editor/src/routes/+page.svelte:380-390` (imports + slot)

**Step 1: Create the component**

`config-editor/src/lib/components/PageBar.svelte`:

```svelte
<script lang="ts">
  import {
    config, currentPage, validationErrors,
    setActivePage, addPage, duplicatePage, deletePage, movePage, updatePageField,
    PAGE_CAP,
  } from '$lib/formStore';
  import type { Page } from '$lib/types';

  let renaming = $state(false);
  let renameValue = $state('');
  let renameInput = $state<HTMLInputElement | null>(null);

  let pages = $derived(($config.pages ?? []) as Page[]);
  let activeIndex = $derived(
    pages.length ? Math.max(0, Math.min(pages.length - 1, $config.active_page ?? 0)) : 0
  );
  let nameError = $derived($validationErrors.get('name'));

  $effect(() => {
    if (renaming) renameInput?.focus();
  });

  function pageLabel(name: string | undefined, i: number): string {
    return name ? `${i + 1}: ${name}` : `Page ${i + 1}`;
  }

  function startRename() {
    renameValue = $currentPage?.name ?? '';
    renaming = true;
  }

  function commitRename() {
    if (!renaming) return;
    renaming = false;
    // Trimmed empty string clears the name (normalizeConfig strips it on save).
    updatePageField('name', renameValue.trim());
  }

  function cancelRename() {
    renaming = false;
  }

  function handleRenameKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter') {
      e.preventDefault();
      commitRename();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      cancelRename();
    }
  }
</script>

<div class="page-bar">
  <label for="page-select">Page</label>
  {#if renaming}
    <input
      id="page-select"
      class="rename-input"
      type="text"
      maxlength="24"
      placeholder="Page name"
      bind:this={renameInput}
      bind:value={renameValue}
      onblur={commitRename}
      onkeydown={handleRenameKeydown}
    />
  {:else}
    <select
      id="page-select"
      value={activeIndex}
      onchange={(e) => setActivePage(Number(e.currentTarget.value))}
    >
      {#each pages as page, i (page.__uiId ?? i)}
        <option value={i}>{pageLabel(page.name, i)}</option>
      {/each}
    </select>
  {/if}

  <div class="page-actions">
    <button
      type="button"
      onclick={() => movePage(activeIndex, activeIndex - 1)}
      disabled={renaming || activeIndex === 0}
      title="Move page earlier"
      aria-label="Move page earlier"
    >◀</button>
    <button
      type="button"
      onclick={() => movePage(activeIndex, activeIndex + 1)}
      disabled={renaming || activeIndex >= pages.length - 1}
      title="Move page later"
      aria-label="Move page later"
    >▶</button>
    <button type="button" onclick={addPage} disabled={renaming || pages.length >= PAGE_CAP}>
      Add
    </button>
    <button
      type="button"
      onclick={() => duplicatePage(activeIndex)}
      disabled={renaming || pages.length >= PAGE_CAP}
    >
      Duplicate
    </button>
    <button type="button" onclick={startRename} disabled={renaming}>
      Rename
    </button>
    <button
      type="button"
      onclick={() => deletePage(activeIndex)}
      disabled={renaming || pages.length <= 1}
    >
      Delete
    </button>
  </div>

  {#if nameError}
    <span class="error">{nameError}</span>
  {/if}
</div>

<style>
  .page-bar {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    padding: 10px 12px;
    margin-bottom: 12px;
    background-color: var(--color-bg-secondary);
    border: 1px solid var(--color-border);
    border-radius: 6px;
  }

  label {
    font-size: 13px;
    font-weight: 600;
    color: var(--color-text-secondary);
  }

  select,
  .rename-input {
    padding: 5px 8px;
    font-size: 13px;
    background-color: var(--color-bg);
    color: var(--color-text);
    border: 1px solid var(--color-border);
    border-radius: 4px;
    min-width: 160px;
  }

  .page-actions {
    display: flex;
    gap: 6px;
  }

  .page-actions button {
    padding: 4px 10px;
    font-size: 13px;
    border-radius: 4px;
    border: 1px solid var(--color-border);
    background-color: var(--color-bg);
    color: var(--color-text);
    cursor: pointer;
  }

  .page-actions button:hover:not(:disabled) {
    background-color: var(--color-bg-hover);
  }

  .page-actions button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .error {
    color: var(--error-text, #f48771);
    font-size: 12px;
  }
</style>
```

**Step 2: Wire it into the app shell**

In `config-editor/src/routes/+page.svelte`:

- Add the import next to the other section imports (line 17 area):

```ts
  import PageBar from '$lib/components/PageBar.svelte';
```

- Insert into the `ConfigForm` children between `DeviceSection` and `ButtonsSection` (line 380-381). Device-wide sections (Device, Display, MIDI Thru, Firmware) stay where they are — the bar sits above exactly the page-scoped sections (Buttons/Encoder/Expression):

```svelte
      <ConfigForm onSave={saveToDevice}>
        <DeviceSection />
        <PageBar />
        <ButtonsSection />
        <EncoderSection />
        <ExpressionSection />
        <DisplaySection />
        <MidiThruSection />
```

**Step 3: Type-check (this is the component's test gate)**

```bash
cd config-editor && npm run check
```

Expected: 0 errors, **0 warnings** (a11y warnings fail the repo bar — fix any before committing).

**Step 4: Run all frontend tests** (`npx vitest run` → all PASS)

**Step 5: Commit**

```bash
git add config-editor/src/lib/components/PageBar.svelte config-editor/src/routes/+page.svelte
git commit -m "Add PageBar (#15 P4a, D1/D4): page select + Add/Duplicate/Rename/Delete/reorder above page-scoped sections"
```

---

### Task 13: Full verification + manual smoke

**Step 1: Full suite**

```bash
./tools/test-all.sh
```

Expected: `ALL GREEN` — pytest, cargo test, svelte-check, **vitest (new step)**, generate:types diff, ruff, mpy-cross, clippy. Fix anything red before proceeding; commit fixes individually.

**Step 2: Manual smoke checklist (needs `npm run tauri dev` + a device or dev config)**

Not automatable — record results in the session file:

1. Page bar renders between Device and Buttons sections; shows `Page 1` for a single-page config.
2. Add → new page with device-sized default buttons, selector jumps to it, dirty dot appears.
3. Duplicate → copy inserted after current, selected.
4. Rename → inline input, Enter commits (option text updates), Escape cancels, >24 chars blocked by `maxlength`.
5. Delete disabled at 1 page; ◀▶ reorder moves the page and selection follows.
6. Undo (⌘Z) reverses each CRUD op in one step.
7. Put a bad value on page 2 (e.g. CC 200 via View JSON check on a hand-edited config), switch to page 1, Save → blocked, footer shows `Page 2 …` line.
8. Save a multi-page config, restart device → boots into the page selected at save time (D2).

**Step 3: Update session file** (`~/.claude/session-midi-captain-max-15-pages-p4.md`) with outcome + next sub-phase (P4b).

---

## Out of scope for P4a (later sub-phases)

- Button `page_step`/`page` inputs + `page_control` section → **P4b** (independent, can run parallel).
- Per-page display/global_channel override UI + firmware font reload → **P4c** (needs RAM probe gate).
- Page templates (Rust commands, dialog capability) → **P4d**.
- Dead `read_config`/`write_config` removal + Python empty-pages guard → ride along with whichever sub-phase touches those areas.
