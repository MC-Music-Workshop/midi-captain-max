# Issue #15 P4b — Form Widgets for Shipped Firmware Features Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Give the two page features the firmware already ships (P3 button page triggers, P3b MIDI-IN CC `page_control`) their missing editor widgets: type-specific `page_step`/`page` inputs on buttons, and a device-wide MIDI Page Control section — each validated in both layers (client + Rust) and covered by e2e specs from day one.

**Architecture:** No schema changes — every field exists in `config.schema.json` and `types.generated.ts`. Button inputs ride the existing `ButtonRow` type-branch idiom and the `PAGE_SCOPED_PATH` seam untouched (button paths route through it as before). The new `PageControlSection` is device-wide (Accordion idiom, plain `updateField`); because `setNestedValue` **throws on missing intermediates** (`formStore.ts:194-249`), every page_control write replaces the whole object at the root path. Validation: client branches are type-gated in `validatePage` (which gains a `pageCount` param for the cross-field `page` check); Rust gains the matching type-gated button checks (`page_control` ranges are already validated at `config.rs:729-770`).

**Tech Stack:** Svelte 5 (runes) + Tauri 2, TypeScript, Vitest, Playwright e2e (WebKit + Tauri IPC mock, added on this branch — `config-editor/e2e/`), Rust (`config.rs`).

**Design doc:** `docs/plans/2026-07-04-issue-15-P4-editor-pages-design.md` — P4b section + decisions D1–D10 govern this plan. Do not re-litigate them.

**Branch:** `15-pages-p4` (this worktree, P4a already merged into it). Commit after every task.

**Firmware semantics the widgets must mirror** (verified in `firmware/dev/core/config.py:144-194`):
- Button `page_step` ≥ 1 (schema `minimum: 1`); firmware wraps with modulo.
- Button `page` is a **0-based** absolute index; firmware clamps, editor fails loud (P1 asymmetry rule). ⚠ Open P3b hardware check: if OEM-style jumps turn out 1-based, only the hint text here follows — the field stays 0-based.
- `page_control`: absent block = off; present block defaults `enabled: true`. `channel` absent = any channel. Inc/dec fire only when the incoming value equals the slot's `value` (default **127**) and move by `page_step` (default 1, wraps). Jump slot has only `cc`; the incoming CC *value* is the target page.

---

## Preflight (no commit)

Fresh-worktree gotchas (see `config-editor/AGENTS.md`):

```bash
./tools/bundle-firmware-for-dev.sh          # idempotent; stages firmware + CP .uf2
cd config-editor && npm install --no-audit --no-fund
npx playwright install webkit               # idempotent; e2e browser
cd ..
```

Sanity: `(cd config-editor/src-tauri && cargo test)` and `(cd config-editor && npm test)` should pass before you start.

---

### Task 1: Client validation — button `page_step`/`page` branches (type-gated)

The bug this fixes: `page_step`/`page` are JSON-only today — no validation in either layer, so `page_step: 0` or a jump to a deleted page dies as an opaque save error (or silently no-ops on the device). Checks are **type-gated**: switching a button's type leaves old fields behind (existing editor behavior for all types), and a stale `page` on a now-`cc` button must not block save — especially since no input would be rendered to fix it.

`validatePage` gains a required `pageCount` param for the cross-field `page` check. Only two callers exist, both in `validation.ts` (`validateConfig`, `validateAllPages`) — grep to confirm nothing else imports `validatePage` before changing the signature.

**Files:**
- Modify: `config-editor/src/lib/validation.ts` (validators map at `:12-98`, `validatePage` at `:103`, msgType chain at `:168-210`, both callers at `:418-461`)
- Modify: `config-editor/src/lib/validation.test.ts`

**Step 1: Write the failing tests**

Append to `validation.test.ts` (the existing `twoPageConfig` helper has an intentionally bad page — don't reuse it here):

```ts
describe('page trigger button fields (P4b)', () => {
  // Two valid pages; page indices 0 and 1 exist, 2 does not.
  function pageTriggerConfig(btn: Record<string, unknown>): MidiCaptainConfig {
    return {
      device: 'one1',
      active_page: 0,
      pages: [
        { name: 'Home', buttons: [{ label: 'GO', color: 'green', ...btn } as never] },
        { name: 'Solo', buttons: [{ label: 'OK', cc: 20, color: 'green' }] },
      ],
    };
  }

  it('rejects page_step < 1 on page_inc', () => {
    const result = validateConfig(pageTriggerConfig({ type: 'page_inc', page_step: 0 }));
    expect(result.errors.get('buttons[0].page_step')).toContain('at least 1');
  });

  it('rejects a page_jump target outside the page list', () => {
    const result = validateConfig(pageTriggerConfig({ type: 'page_jump', page: 2 }));
    expect(result.errors.get('buttons[0].page')).toContain('between 0 and 1');
  });

  it('accepts a valid page_jump target', () => {
    expect(validateConfig(pageTriggerConfig({ type: 'page_jump', page: 1 })).isValid).toBe(true);
  });

  it('ignores stale page fields on a non-page-type button (type-gated)', () => {
    expect(validateConfig(pageTriggerConfig({ type: 'cc', cc: 20, page: 99 })).isValid).toBe(true);
  });
});
```

**Step 2: Run to verify failure**

```bash
cd config-editor && npx vitest run src/lib/validation.test.ts
```

Expected: first two tests FAIL (`undefined` doesn't contain the message); last two pass already — they lock the gating in.

**Step 3: Implement**

In `validation.ts`, add to the `validators` map (after `pcStep`):

```ts
  pageStep: (value: number): string | null => {
    if (!Number.isInteger(value)) return 'Step must be an integer';
    if (value < 1) return 'Step must be at least 1';
    return null;
  },
```

(No upper bound: the schema has none — the firmware wraps. Rust's `Option<u8>` rejects >255 at parse time anyway.)

Change the `validatePage` signature:

```ts
export function validatePage(page: Page, device: MidiCaptainConfig['device'], pageCount: number): Map<string, string> {
```

In the per-button `msgType` chain, insert between the `pc_inc`/`pc_dec` branch and the `hid` branch:

```ts
    } else if (msgType === 'page_inc' || msgType === 'page_dec') {
      if (btn.page_step !== undefined) {
        const stepError = validators.pageStep(btn.page_step);
        if (stepError) errors.set(`buttons[${idx}].page_step`, stepError);
      }
    } else if (msgType === 'page_jump') {
      // Cross-field: the firmware clamps a bad target, the editor fails loud
      // (P1 asymmetry rule). 0-based, so max is pageCount - 1.
      if (btn.page !== undefined) {
        if (!Number.isInteger(btn.page) || btn.page < 0 || btn.page >= pageCount) {
          errors.set(`buttons[${idx}].page`, `Target page must be between 0 and ${pageCount - 1} (0-based)`);
        }
      }
```

Update both callers — in `validateConfig` and `validateAllPages`, compute once above the `validatePage` call(s):

```ts
  const pageCount = pages.length || 1;
```

and pass it: `validatePage(page, config.device, pageCount)`.

**Step 4: Run tests to verify they pass** (`npx vitest run` — full suite; P4a tests must stay green)

**Step 5: Type-check** (`cd config-editor && npm run check` → 0 errors, 0 warnings)

**Step 6: Commit**

```bash
git add config-editor/src/lib/validation.ts config-editor/src/lib/validation.test.ts
git commit -m "Client-validate button page_step/page (type-gated); validatePage gains pageCount (#15 P4b)"
```

---

### Task 2: Rust `validate()` — button `page_step`/`page` checks (type-gated)

Same checks, Rust layer, inside the existing per-page button loop so errors get the `Page N, ` prefix. Type-gated for the same stale-field reason as Task 1. Use `matches!` for the type test — it doesn't require `PartialEq` on `MessageType`.

**Files:**
- Modify: `config-editor/src-tauri/src/config.rs` (button loop at `:596-641`, tests module)

**Step 1: Write the failing tests**

In `config.rs` `mod tests`, add (same `parse_migrated` idiom as `test_validate_rejects_long_page_name`):

```rust
#[test]
fn test_validate_rejects_zero_page_step() {
    let json = r#"{
        "device": "one1",
        "pages": [{
            "buttons": [{"label": "PG", "color": "green", "type": "page_inc", "page_step": 0}]
        }],
        "active_page": 0
    }"#;

    let config = parse_migrated(json);
    let errors = config.validate().unwrap_err();
    assert!(
        errors.iter().any(|e| e.contains("Page 1") && e.contains("page_step")),
        "expected page_step error, got: {errors:?}"
    );
}

#[test]
fn test_validate_rejects_page_jump_target_out_of_range() {
    // One page, so target index 1 does not exist.
    let json = r#"{
        "device": "one1",
        "pages": [{
            "buttons": [{"label": "PG", "color": "green", "type": "page_jump", "page": 1}]
        }],
        "active_page": 0
    }"#;

    let config = parse_migrated(json);
    let errors = config.validate().unwrap_err();
    assert!(
        errors.iter().any(|e| e.contains("Page 1") && e.contains("out of range (0-0)")),
        "expected page-target error, got: {errors:?}"
    );
}

#[test]
fn test_validate_ignores_stale_page_fields_on_other_types() {
    // Type-gated: a stale `page` left behind by an editor type switch must not
    // block save (no input is rendered for it on a cc button).
    let json = r#"{
        "device": "one1",
        "pages": [{
            "buttons": [{"label": "OK", "cc": 20, "color": "green", "page": 99, "page_step": 0}]
        }],
        "active_page": 0
    }"#;

    assert!(parse_migrated(json).validate().is_ok());
}
```

**Step 2: Run to verify failure**

```bash
cd config-editor/src-tauri && cargo test test_validate_rejects_zero_page_step test_validate_rejects_page_jump
```

Expected: FAIL — `validate()` returns `Ok(())`, `unwrap_err` panics (third test passes trivially today; it pins the gating).

**Step 3: Implement**

In the button loop, after the `long_press_threshold_ms` check (`config.rs:625-629`) and before the `mode == ButtonMode::Keytimes` block, add:

```rust
                // Page-switch trigger fields (#15 P4b). Type-gated: a stale page/page_step
                // left behind by an editor type switch must not block save. The firmware
                // clamps a bad jump target; the editor fails loud (P1 asymmetry rule).
                if matches!(button.message_type, MessageType::PageInc | MessageType::PageDec) {
                    if let Some(step) = button.page_step {
                        if step < 1 {
                            errors.push(format!("{}Button {} page_step must be >= 1", pfx, i + 1));
                        }
                    }
                }
                if matches!(button.message_type, MessageType::PageJump) {
                    if let Some(pg) = button.page {
                        if (pg as usize) >= self.pages.len() {
                            errors.push(format!(
                                "{}Button {} page {} out of range (0-{})",
                                pfx, i + 1, pg, self.pages.len().saturating_sub(1)
                            ));
                        }
                    }
                }
```

**Step 4: Run the full crate** (`cargo test` — whole suite, not just the new tests)

**Step 5: Commit**

```bash
git add config-editor/src-tauri/src/config.rs
git commit -m "Rust validate(): button page_step >= 1 and page_jump target in range, type-gated (#15 P4b)"
```

---

### Task 3: ButtonRow — `page_step` and Target Page inputs

The missing type branches in the `ButtonRow` field chain. `page_jump` gets a 0-based index input plus a hint naming the resolved target page (design: "a hint showing the page name"). Follows the `isPCIncDec` idiom exactly: number input, commit `onblur`, schema default as the displayed fallback value. Button paths go through `onUpdate` → `buttons[i].field` → `PAGE_SCOPED_PATH` — no seam work.

Accessibility bar (repo convention: **0 svelte-check warnings**): label/`for` pairing, Svelte 5 event syntax.

**Files:**
- Modify: `config-editor/src/lib/components/ButtonRow.svelte` (script `:1-238`, type chain `:299-411`)

**Step 1: Script additions**

Extend the formStore import (line 6) with `config`:

```ts
  import { validationErrors, syncButtonStates, selectGroupNames, config } from '$lib/formStore';
```

After the `isPageType` derived (line 34), add:

```ts
  let isPageIncDec = $derived(msgType === 'page_inc' || msgType === 'page_dec');
  let isPageJump = $derived(msgType === 'page_jump');
  let pageCount = $derived(($config.pages ?? []).length);
  // Resolved target for the page_jump hint: the field is a 0-based index, so
  // name the page it lands on. Null when out of range — the error text owns that.
  let jumpTarget = $derived.by(() => {
    if (!isPageJump) return null;
    const idx = button.page ?? 0;
    const target = ($config.pages ?? [])[idx];
    if (!target) return null;
    return target.name ? `“${target.name}”` : `Page ${idx + 1}`;
  });
```

After `handlePCStepChange` (line 126), add:

```ts
  function handlePageStepChange(e: Event) {
    const target = e.target as HTMLInputElement;
    onUpdate('page_step', target.value === '' ? undefined : parseInt(target.value));
  }

  function handlePageChange(e: Event) {
    const target = e.target as HTMLInputElement;
    onUpdate('page', target.value === '' ? undefined : parseInt(target.value));
  }
```

After the `pcStepError` derived (line 227), add:

```ts
  let pageStepError = $derived($validationErrors.get(`${basePath}.page_step`));
  let pageError = $derived($validationErrors.get(`${basePath}.page`));
```

**Step 2: Template branches**

In the type-specific chain, insert between the `{:else if isPCIncDec}` block (ends line 359) and `{:else if isHID}`:

```svelte
  {:else if isPageIncDec}
    <div class="field">
      <label class="field-label" for={fieldId('page-step')}>Step:</label>
      <input id={fieldId('page-step')} type="number" class="input-cc" class:error={!!pageStepError}
        value={button.page_step ?? 1} onblur={handlePageStepChange} disabled={disabled}
        min="1" title="Pages to move per press; wraps at the ends." />
      {#if pageStepError}<span class="error-text">{pageStepError}</span>{/if}
    </div>
  {:else if isPageJump}
    <div class="field">
      <label class="field-label" for={fieldId('page')}>Target Page:</label>
      <input id={fieldId('page')} type="number" class="input-cc" class:error={!!pageError}
        value={button.page ?? 0} onblur={handlePageChange} disabled={disabled}
        min="0" max={pageCount - 1} title="0-based page index (0 = first page)." />
      {#if pageError}
        <span class="error-text">{pageError}</span>
      {:else if jumpTarget}
        <span class="hint-text">→ {jumpTarget}</span>
      {/if}
    </div>
```

(`.hint-text` already exists in this component's styles.)

**Step 3: Type-check + tests**

```bash
cd config-editor && npm run check && npx vitest run
```

Expected: 0 errors, **0 warnings**; all vitest suites PASS.

**Step 4: Commit**

```bash
git add config-editor/src/lib/components/ButtonRow.svelte
git commit -m "Add page_step / Target Page inputs to ButtonRow with named-page jump hint (#15 P4b)"
```

---

### Task 4: e2e spec — button page-trigger inputs

New inputs get e2e coverage from day one (harness landed on this branch: WebKit + Tauri IPC mock, `config-editor/e2e/helpers.ts`). Key harness fact: **fields commit on blur, and in WebKit a click does not blur a focused input** — always call `.blur()` explicitly after `.fill()`. `twoPageConfig()` in helpers has pages named `A`/`B` with distinct button data.

**Files:**
- Create: `config-editor/e2e/page-trigger-buttons.spec.ts`

**Step 1: Write the spec**

```ts
import { test, expect } from '@playwright/test';
import { loadApp, twoPageConfig, readStoreJson } from './helpers';

// P4b button page-trigger inputs: type-specific fields commit on blur and land
// in the store JSON exactly as the firmware expects them.

test('page_jump gets a target input with a named-page hint', async ({ page }) => {
  await loadApp(page, twoPageConfig());
  await page.locator('#btn-0-type').selectOption('page_jump');

  const target = page.locator('#btn-0-page');
  await target.fill('1');
  await target.blur();

  await expect(page.locator('.button-row .hint-text')).toHaveText('→ “B”');
  const json = await readStoreJson(page);
  expect(json.pages[0].buttons[0]).toMatchObject({ type: 'page_jump', page: 1 });
});

test('page_jump target outside the page list shows an inline error', async ({ page }) => {
  await loadApp(page, twoPageConfig());
  await page.locator('#btn-0-type').selectOption('page_jump');

  const target = page.locator('#btn-0-page');
  await target.fill('5');
  await target.blur();

  await expect(page.locator('.button-row .error-text')).toHaveText(/between 0 and 1/);
});

test('page_inc gets a step input', async ({ page }) => {
  await loadApp(page, twoPageConfig());
  await page.locator('#btn-0-type').selectOption('page_inc');

  const step = page.locator('#btn-0-page-step');
  await step.fill('2');
  await step.blur();

  const json = await readStoreJson(page);
  expect(json.pages[0].buttons[0]).toMatchObject({ type: 'page_inc', page_step: 2 });
});
```

**Step 2: Run it**

```bash
cd config-editor && npx playwright test e2e/page-trigger-buttons.spec.ts
```

Expected: 3 PASS (the config's `webServer` starts `npm run dev` on 1420, or reuses a running one). Also run the full e2e suite once (`npx playwright test`) to confirm no regressions.

**Step 3: Commit**

```bash
git add config-editor/e2e/page-trigger-buttons.spec.ts
git commit -m "e2e: page trigger button inputs — jump target + hint, range error, inc step (#15 P4b)"
```

---

### Task 5: Client validation — `page_control` block

Mirrors the Rust ranges (`config.rs:729-770`) so bad values fail inline instead of as an opaque save error. Device-wide → the checks live in `validateConfig` (next to `usb_drive_name`), **not** `validatePage`. Error keys are the field paths the new section will look up (`page_control.jump.cc` etc.) — device-wide keys are unprefixed by convention.

**Files:**
- Modify: `config-editor/src/lib/validation.ts` (`validateConfig`, `:418+`)
- Modify: `config-editor/src/lib/validation.test.ts`

**Step 1: Write the failing tests**

Append:

```ts
describe('page_control validation (P4b)', () => {
  function pcConfig(pc: unknown): MidiCaptainConfig {
    return {
      device: 'one1',
      active_page: 0,
      pages: [{ buttons: [{ label: 'OK', cc: 20, color: 'green' }] }],
      page_control: pc as MidiCaptainConfig['page_control'],
    };
  }

  it('accepts a full valid block', () => {
    const result = validateConfig(pcConfig({
      enabled: true, channel: 0,
      jump: { cc: 20 }, inc: { cc: 21, value: 127, page_step: 1 }, dec: { cc: 22 },
    }));
    expect(result.isValid).toBe(true);
  });

  it('rejects out-of-range slot fields with per-field keys', () => {
    const result = validateConfig(pcConfig({
      jump: { cc: 200 }, inc: { cc: 21, value: 300, page_step: 0 },
    }));
    expect(result.errors.get('page_control.jump.cc')).toContain('127');
    expect(result.errors.get('page_control.inc.value')).toContain('127');
    expect(result.errors.get('page_control.inc.page_step')).toContain('at least 1');
  });

  it('rejects an out-of-range channel', () => {
    const result = validateConfig(pcConfig({ channel: 16, jump: { cc: 20 } }));
    expect(result.errors.get('page_control.channel')).toBeTruthy();
  });
});
```

**Step 2: Run to verify failure** (`npx vitest run src/lib/validation.test.ts` → the two rejection tests FAIL)

**Step 3: Implement**

In `validateConfig`, after the `usb_drive_name` block:

```ts
  // MIDI-IN CC page control (#15 P3b): device-wide, so it validates here, not
  // per page. Mirrors the Rust ranges in config.rs so bad values fail inline
  // instead of as an opaque save error. channel may be null (= any channel).
  const pc = config.page_control;
  if (pc) {
    if (pc.channel !== undefined && pc.channel !== null) {
      const chError = validators.channel(pc.channel);
      if (chError) errors.set('page_control.channel', chError);
    }
    if (pc.jump?.cc !== undefined) {
      const ccError = validators.cc(pc.jump.cc);
      if (ccError) errors.set('page_control.jump.cc', ccError);
    }
    for (const key of ['inc', 'dec'] as const) {
      const slot = pc[key];
      if (!slot) continue;
      const p = `page_control.${key}`;
      if (slot.cc !== undefined) {
        const ccError = validators.cc(slot.cc);
        if (ccError) errors.set(`${p}.cc`, ccError);
      }
      if (slot.value !== undefined) {
        const vError = validators.withinRange(slot.value, 0, 127);
        if (vError) errors.set(`${p}.value`, vError);
      }
      if (slot.page_step !== undefined) {
        const sError = validators.pageStep(slot.page_step);
        if (sError) errors.set(`${p}.page_step`, sError);
      }
    }
  }
```

**Step 4: Run tests to verify they pass** (`npx vitest run` — full suite)

**Step 5: Type-check** (`npm run check` → 0 errors, 0 warnings)

**Step 6: Commit**

```bash
git add config-editor/src/lib/validation.ts config-editor/src/lib/validation.test.ts
git commit -m "Client-validate page_control block, mirroring Rust ranges (#15 P4b)"
```

---

### Task 6: `PageControlSection.svelte` + wiring

The P3b promise lands here: "clean editor UI later (3 rows, no list management)". Accordion section, three fixed rows (Jump / Inc / Dec), no add/remove. Design decisions encoded:

- **Whole-object writes.** `setNestedValue` throws on missing intermediates, so every handler clones `$config.page_control ?? {}`, mutates, and writes `updateField('page_control', next)`. `page_control` doesn't match `PAGE_SCOPED_PATH`, so it stays a root path.
- **Empty CC = slot off** (the slot object is deleted). Inc/dec `value`/`page_step` inputs are disabled until their slot has a CC.
- **The Enabled checkbox reflects firmware semantics**, not a local toggle: absent block = unchecked; present block = `enabled ?? true`. Setting a CC on an absent block therefore checks the box — that's accurate (the block becomes live), not a glitch.
- **Channel displays 1–16, stores 0–15, empty = any** (same convention as button channel).

**Files:**
- Modify: `config-editor/src/lib/types.ts:12-19` (re-export `PageControl`)
- Create: `config-editor/src/lib/components/PageControlSection.svelte`
- Modify: `config-editor/src/routes/+page.svelte` (import + slot after `MidiThruSection`)

**Step 1: Re-export the type**

In `types.ts`, add `PageControl,` to the re-export list (lines 12-19, alongside `DisplayConfig`).

**Step 2: Create the component**

`config-editor/src/lib/components/PageControlSection.svelte`:

```svelte
<script lang="ts">
  import Accordion from './Accordion.svelte';
  import { config, updateField, validationErrors } from '$lib/formStore';
  import type { PageControl } from '$lib/types';

  let pc = $derived($config.page_control);
  // Firmware semantics: absent block = off; present block defaults enabled=true.
  let enabled = $derived(pc ? (pc.enabled ?? true) : false);
  let displayChannel = $derived(pc?.channel != null ? pc.channel + 1 : '');

  function err(key: string): string | undefined {
    return $validationErrors.get(key);
  }

  // setNestedValue throws on missing intermediates, so every write replaces the
  // whole page_control object at its root path instead of dotting into it.
  function write(mutate: (next: PageControl) => void) {
    const next: PageControl = structuredClone($config.page_control ?? {});
    mutate(next);
    updateField('page_control', next);
  }

  function handleEnabledChange(e: Event) {
    const target = e.target as HTMLInputElement;
    write((next) => {
      next.enabled = target.checked;
    });
  }

  function handleChannelChange(e: Event) {
    const target = e.target as HTMLInputElement;
    write((next) => {
      if (target.value === '') {
        delete next.channel; // absent = any channel
      } else {
        // Convert from 1-16 display to 0-15 storage
        next.channel = parseInt(target.value) - 1;
      }
    });
  }

  function handleSlotCcChange(slot: 'jump' | 'inc' | 'dec', e: Event) {
    const target = e.target as HTMLInputElement;
    write((next) => {
      if (target.value === '') {
        delete next[slot]; // empty CC disables the slot entirely
      } else if (slot === 'jump') {
        next.jump = { ...next.jump, cc: parseInt(target.value) };
      } else {
        next[slot] = { ...next[slot], cc: parseInt(target.value) };
      }
    });
  }

  function handleSlotFieldChange(slot: 'inc' | 'dec', field: 'value' | 'page_step', e: Event) {
    const target = e.target as HTMLInputElement;
    write((next) => {
      const s = next[slot];
      if (!s) return; // inputs are disabled until the slot has a CC
      if (target.value === '') {
        delete s[field];
      } else {
        s[field] = parseInt(target.value);
      }
    });
  }
</script>

<Accordion title="MIDI Page Control">
  <div class="page-control-section">
    <p class="section-help">
      Let an inbound MIDI Control Change switch the active page. The Jump CC's
      incoming <em>value</em> is the target page (0-based). Inc/Dec fire only when
      the incoming value equals the trigger value (default 127) and move by the
      step, wrapping at the ends. A slot with an empty CC is off.
    </p>

    <div class="header-row">
      <label class="enable-cell">
        <input type="checkbox" checked={enabled} onchange={handleEnabledChange} />
        <span>Enabled</span>
      </label>
      <div class="field">
        <label class="field-label" for="page-control-channel">Channel:</label>
        <input
          id="page-control-channel"
          type="number"
          class="input-num"
          class:error={!!err('page_control.channel')}
          value={displayChannel}
          onblur={handleChannelChange}
          min="1"
          max="16"
          placeholder="Any"
          title="Only react on this MIDI channel; empty = any channel."
        />
        {#if err('page_control.channel')}
          <span class="error-text">{err('page_control.channel')}</span>
        {/if}
      </div>
    </div>

    <table class="pc-table">
      <thead>
        <tr>
          <th scope="col" class="corner">Slot</th>
          <th scope="col">CC</th>
          <th scope="col">Trigger Value</th>
          <th scope="col">Step</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <th scope="row">Jump</th>
          <td>
            <input
              id="page-control-jump-cc"
              type="number"
              class="input-num"
              class:error={!!err('page_control.jump.cc')}
              value={pc?.jump?.cc ?? ''}
              onblur={(e) => handleSlotCcChange('jump', e)}
              min="0"
              max="127"
              placeholder="Off"
              aria-label="Jump CC number"
            />
            {#if err('page_control.jump.cc')}
              <span class="error-text">{err('page_control.jump.cc')}</span>
            {/if}
          </td>
          <td class="na" colspan="2">incoming value = target page (0-based)</td>
        </tr>
        {#each [['inc', 'Inc', pc?.inc], ['dec', 'Dec', pc?.dec]] as const as [key, label, slot] (key)}
          <tr>
            <th scope="row">{label}</th>
            <td>
              <input
                id={`page-control-${key}-cc`}
                type="number"
                class="input-num"
                class:error={!!err(`page_control.${key}.cc`)}
                value={slot?.cc ?? ''}
                onblur={(e) => handleSlotCcChange(key, e)}
                min="0"
                max="127"
                placeholder="Off"
                aria-label={`${label} CC number`}
              />
              {#if err(`page_control.${key}.cc`)}
                <span class="error-text">{err(`page_control.${key}.cc`)}</span>
              {/if}
            </td>
            <td>
              <input
                id={`page-control-${key}-value`}
                type="number"
                class="input-num"
                class:error={!!err(`page_control.${key}.value`)}
                value={slot?.value ?? ''}
                onblur={(e) => handleSlotFieldChange(key, 'value', e)}
                disabled={!slot}
                min="0"
                max="127"
                placeholder="127"
                aria-label={`${label} trigger value`}
              />
              {#if err(`page_control.${key}.value`)}
                <span class="error-text">{err(`page_control.${key}.value`)}</span>
              {/if}
            </td>
            <td>
              <input
                id={`page-control-${key}-step`}
                type="number"
                class="input-num"
                class:error={!!err(`page_control.${key}.page_step`)}
                value={slot?.page_step ?? ''}
                onblur={(e) => handleSlotFieldChange(key, 'page_step', e)}
                disabled={!slot}
                min="1"
                placeholder="1"
                aria-label={`${label} page step`}
              />
              {#if err(`page_control.${key}.page_step`)}
                <span class="error-text">{err(`page_control.${key}.page_step`)}</span>
              {/if}
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
</Accordion>

<style>
  .page-control-section {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .section-help {
    font-size: 0.875rem;
    color: #666;
    margin: 0;
  }

  .header-row {
    display: flex;
    align-items: flex-start;
    gap: 1.5rem;
  }

  .enable-cell {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    cursor: pointer;
    padding-top: 1.1rem; /* aligns with the channel input beside its label */
  }

  .enable-cell input[type='checkbox'] {
    width: 16px;
    height: 16px;
    cursor: pointer;
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .field-label {
    font-size: 0.75rem;
    color: #666;
  }

  .pc-table {
    border-collapse: collapse;
    align-self: flex-start;
    font-size: 0.9rem;
  }

  .pc-table th,
  .pc-table td {
    border: 1px solid #d0d0d0;
    padding: 0.5rem 0.75rem;
    text-align: left;
    vertical-align: top;
  }

  .pc-table thead th {
    background: #f3f3f3;
    font-weight: 600;
  }

  .pc-table tbody th {
    background: #f8f8f8;
    font-weight: 600;
  }

  .pc-table .corner {
    color: #888;
    font-weight: 500;
  }

  .pc-table .na {
    color: #888;
    font-size: 0.8125rem;
    font-style: italic;
  }

  .input-num {
    width: 70px;
    padding: 0.375rem 0.5rem;
    border: 1px solid #ccc;
    border-radius: 4px;
    font-size: 0.875rem;
  }

  input.error {
    border-color: #dc3545;
  }

  .error-text {
    display: block;
    font-size: 0.75rem;
    color: #dc3545;
    margin-top: 2px;
  }

  input:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
</style>
```

(If svelte-check balks at the `{#each [...] as const as [key, label, slot]}` tuple typing, fall back to two hand-written `<tr>` blocks for Inc and Dec — identical markup, `inc`/`dec` literals inlined. Content over cleverness.)

**Step 3: Wire it into the app shell**

In `config-editor/src/routes/+page.svelte`:

- Import next to the other sections (line 23 area):

```ts
  import PageControlSection from '$lib/components/PageControlSection.svelte';
```

- Insert after `<MidiThruSection />` (line 402) — it's device-wide, so it lives with the other device-wide sections below the page-scoped group:

```svelte
        <MidiThruSection />
        <PageControlSection />
```

**Step 4: Type-check + tests**

```bash
cd config-editor && npm run check && npx vitest run
```

Expected: 0 errors, **0 warnings** (a11y warnings fail the repo bar); all vitest suites PASS.

**Step 5: Commit**

```bash
git add config-editor/src/lib/types.ts config-editor/src/lib/components/PageControlSection.svelte config-editor/src/routes/+page.svelte
git commit -m "Add MIDI Page Control section (#15 P4b): 3-slot jump/inc/dec editor for P3b page_control"
```

---

### Task 7: e2e spec — MIDI Page Control section

**Files:**
- Create: `config-editor/e2e/page-control.spec.ts`

**Step 1: Write the spec**

```ts
import { test, expect } from '@playwright/test';
import { loadApp, twoPageConfig, readStoreJson } from './helpers';

// P4b MIDI Page Control section. Writes replace the whole page_control object
// (store paths can't create missing intermediates), so the JSON shape after
// each edit is the contract to pin down.

test('configuring jump and inc slots lands the P3b shape in the store', async ({ page }) => {
  await loadApp(page, twoPageConfig());

  const jumpCc = page.locator('#page-control-jump-cc');
  await jumpCc.fill('20');
  await jumpCc.blur();

  const incCc = page.locator('#page-control-inc-cc');
  await incCc.fill('21');
  await incCc.blur();

  const incStep = page.locator('#page-control-inc-step');
  await expect(incStep).toBeEnabled(); // unlocked once the slot has a CC
  await incStep.fill('2');
  await incStep.blur();

  const json = await readStoreJson(page);
  expect(json.page_control).toEqual({ jump: { cc: 20 }, inc: { cc: 21, page_step: 2 } });
});

test('clearing a slot CC removes the slot; Enabled reflects the block', async ({ page }) => {
  await loadApp(page, { ...twoPageConfig(), page_control: { enabled: true, jump: { cc: 20 } } });

  const enabledBox = page.locator('.page-control-section input[type="checkbox"]');
  await expect(enabledBox).toBeChecked();
  await expect(page.locator('#page-control-inc-value')).toBeDisabled(); // no inc slot yet

  const jumpCc = page.locator('#page-control-jump-cc');
  await jumpCc.fill('');
  await jumpCc.blur();

  const json = await readStoreJson(page);
  expect(json.page_control.jump).toBeUndefined();
  expect(json.page_control.enabled).toBe(true);
});

test('out-of-range CC shows an inline error', async ({ page }) => {
  await loadApp(page, twoPageConfig());

  const jumpCc = page.locator('#page-control-jump-cc');
  await jumpCc.fill('200');
  await jumpCc.blur();

  await expect(page.locator('.page-control-section .error-text')).toHaveText(/0 and 127/);
});
```

**Step 2: Run the full e2e suite**

```bash
cd config-editor && npx playwright test
```

Expected: all specs PASS (new + P4a's page-crud / page-switch-edit / edit-pages-modal).

**Step 3: Commit**

```bash
git add config-editor/e2e/page-control.spec.ts
git commit -m "e2e: MIDI Page Control section — slot shape, slot removal, inline range error (#15 P4b)"
```

---

### Task 8: Full verification + manual smoke

**Step 1: Full suite**

```bash
./tools/test-all.sh
```

Expected: `ALL GREEN` — pytest, cargo test, svelte-check, vitest, generate:types diff, ruff, mpy-cross, clippy. (E2e is not part of test-all.sh — it was run per-task above; run `cd config-editor && npx playwright test` once more here if anything changed since Task 7.)

**Step 2: Manual smoke checklist (needs `npm run tauri dev` + a device or dev config)**

Not automatable — record results in the session file:

1. Set a button to `Page Jump` → Target Page input appears with `→ “<name>”` hint; hint tracks renames and page reorders.
2. Target Page 5 on a 2-page config → inline error; Save blocked.
3. Set a button to `Page+` with Step 2 on a 3-page config, save to device → each press advances 2 pages, wrapping.
4. MIDI Page Control: enable, Jump CC 20, save → send `CC20 val 1` from a DAW → device switches to page 2 (**0-based check**: if the device lands elsewhere, the P3b hardware question just answered itself — record it, don't fix here).
5. Inc slot CC 21, trigger value default → `CC21 val 127` advances a page; other values don't.
6. Hand-edit a config with `page_control.jump.cc: 200` via View JSON → inline error in the section.

**Step 3: Update the session file** (`~/.claude/session-midi-captain-max-15-pages-p4.md`) with outcome + next sub-phase (P4c: per-page overrides — starts with the mandatory RAM probe gate).

---

## Out of scope for P4b (later sub-phases / ride-alongs)

- Per-page display/global_channel override UI + firmware font reload → **P4c** (RAM probe gate first).
- Page templates (Rust commands, dialog capability) → **P4d**.
- Dead `read_config`/`write_config` removal → rides with **P4d** (that's the sub-phase touching `commands.rs`/`lib.rs`).
- Python empty-pages `validate_config` guard → rides with whichever sub-phase next touches `firmware/dev/core/config.py` (P4b touches no firmware).
- Stale-field cleanup on button type switch (e.g. dropping `page` when switching to `cc`) — pre-existing behavior for every type; validation is type-gated instead, per the simple-uniform-rules preference.
