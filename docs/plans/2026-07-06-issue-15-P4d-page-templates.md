# Issue #15 P4d — Page Templates + Per-Page MIDI Channel Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ship the last two pieces of the #15 editor-pages work — (1) export/import a single page as a reusable JSON **template** (default folder + "anywhere" via file pickers), and (2) a **per-page MIDI channel** override field (moved out of the skipped P4c) — each validated in both layers (client + Rust) and covered by tests.

**Architecture:** Templates are host-side JSON files, one `Page` object per file, handled by new Rust commands (`export_page_template` / `import_page_template` / `list_page_templates` / `page_templates_dir`) in a new `src-tauri/src/templates.rs` module. Import validates the page against the **current device** by wrapping it in a throwaway config and calling the existing `MidiCaptainConfig::validate()` — no new validation logic, no silent reshaping (D9). Template IO uses `std::fs` inside Rust, so it needs **no** JS `fs` capability; the file pickers use `@tauri-apps/plugin-dialog`, whose `dialog:default` set already grants `save` + `open` (verified — see Task 8, this corrects a stale assumption in the design doc). The per-page channel field rides the `updatePageField('global_channel', v)` seam from P4a (D6) and a per-page section rendered inside the existing `{#key currentPage.__uiId}` block.

**Tech Stack:** Rust (`config.rs` validate + new `templates.rs`), Tauri 2 (`lib.rs` handler, `AppHandle` path resolver), Svelte 5 (runes), TypeScript, Vitest, Playwright e2e (WebKit + Tauri IPC mock in `config-editor/e2e/`).

**Design doc:** `docs/plans/2026-07-04-issue-15-P4-editor-pages-design.md` — P4d section + decisions **D6, D7, D8, D9** govern this plan. Do not re-litigate them. Scope note (session file, 2026-07-06): **P4c was skipped**; only the per-page `global_channel` field + its Rust range check moved here. Per-page `display` overrides and the D10 RAM probe did **not** — they wait for the display/fonts rewrite.

**Branch:** `15-pages-p4d` (this worktree). Commit after every task.

**Firmware / schema reality the code must mirror:**
- `Page.global_channel` is `Option<u8>`, stored **0–15**, displayed **1–16**; absent = inherit the device-wide default. Firmware already resolves it (P2). Same 0–15 range as the device-wide `global_channel` and button `channel`.
- A template file is a bare `Page` JSON object (has `buttons`, optional `name`/`encoder`/`expression`/`global_channel`/`display`). No `pages`/`device` wrapper (D7).
- Import re-validates shape against the **current** device (button count, encoder/expression only on STD10) — a page saved from an STD10 must be rejected when imported into a ONE config (D9).

---

## Preflight (no commit)

Fresh-worktree gotchas (see `config-editor/AGENTS.md` + session-file notes):

```bash
cd /Users/maximiliancascone/github/midi-captain-max/.worktrees/15-pages-p4d
./tools/bundle-firmware-for-dev.sh          # idempotent; stages firmware + CP .uf2
cd config-editor && npm install --no-audit --no-fund
npx playwright install webkit               # idempotent; e2e browser
cd ..
```

Sanity (must pass before you start): `(cd config-editor/src-tauri && cargo test)` and `(cd config-editor && npm test)`.

> **Bash cwd resets** — prefix commands with an absolute `cd` (session-file note).

---

# Part A — Per-page MIDI channel (moved from P4c)

### Task 1: Rust `validate()` — per-page `global_channel` 0–15 check

Closes the remaining half of review item #8 (`Page.name` was closed in P4a; per-page `global_channel` is the rest). The check goes inside the existing per-page loop, right after the page-name check, mirroring the device-wide and button channel messages.

**Files:**
- Modify: `config-editor/src-tauri/src/config.rs` (per-page loop, after the `page.name` block at `:581-586`)
- Modify: `config-editor/src-tauri/src/config.rs` `mod tests` (`:854+`)

**Step 1: Write the failing tests**

Append inside `mod tests`:

```rust
#[test]
fn rejects_per_page_global_channel_over_15() {
    // one1 = 1 button/page keeps every other check green.
    let json = r#"{
        "device": "one1",
        "pages": [{ "global_channel": 16, "buttons": [{"label": "B0", "cc": 20, "color": "green"}] }]
    }"#;
    let cfg = parse_migrated(json);
    let errs = cfg.validate().unwrap_err();
    assert!(errs.iter().any(|e| e.contains("global_channel") && e.contains("Page 1")),
        "expected a Page 1 global_channel error, got {errs:?}");
}

#[test]
fn accepts_per_page_global_channel_in_range() {
    let json = r#"{
        "device": "one1",
        "pages": [{ "global_channel": 15, "buttons": [{"label": "B0", "cc": 20, "color": "green"}] }]
    }"#;
    assert!(parse_migrated(json).validate().is_ok());
}
```

**Step 2: Run to verify failure**

```bash
cd config-editor/src-tauri && cargo test rejects_per_page_global_channel_over_15 accepts_per_page_global_channel_in_range
```
Expected: `rejects_…` FAILS (no such error emitted); `accepts_…` already passes.

**Step 3: Implement**

In `config.rs`, inside `for (p, page) in self.pages.iter().enumerate()`, immediately after the `if let Some(ref name) = page.name { … }` block (`:581-586`):

```rust
            // Per-page MIDI channel override (0-15 internally, displayed 1-16).
            // Absent = inherit the device-wide default (firmware resolves this, P2).
            if let Some(ch) = page.global_channel {
                if ch > 15 {
                    errors.push(format!("{}global_channel value {} is invalid (must be 1-16, stored as 0-15)", pfx, ch + 1));
                }
            }
```

**Step 4: Run to verify pass**

```bash
cd config-editor/src-tauri && cargo test rejects_per_page_global_channel_over_15 accepts_per_page_global_channel_in_range
```
Expected: PASS.

**Step 5: Commit**

```bash
git add config-editor/src-tauri/src/config.rs
git commit -m "Validate per-page global_channel 0-15 in Rust (closes review item #8 remainder)"
```

---

### Task 2: Client `validatePage` — per-page `global_channel` check

Reuse the existing `validators.channel` (0–15, message "Channel must be between 1 and 16"). Key is **unprefixed** `global_channel` so the active page's error surfaces inline (locked convention); `validateAllPages` prefixes it for non-active pages automatically.

**Files:**
- Modify: `config-editor/src/lib/validation.ts` (`validatePage`, after the `page.name` check at `:117-119`)
- Modify: `config-editor/src/lib/validation.test.ts`

**Step 1: Write the failing tests**

Append to `validation.test.ts`:

```ts
describe('per-page global_channel (P4d)', () => {
  function cfgWith(ch: number): MidiCaptainConfig {
    return {
      device: 'one1',
      active_page: 0,
      pages: [{ name: 'Home', global_channel: ch, buttons: [{ label: 'B0', cc: 20, color: 'green' }] }],
    } as never;
  }

  it('rejects a per-page channel above 15 (active page, unprefixed key)', () => {
    expect(validateConfig(cfgWith(16)).errors.get('global_channel')).toContain('between 1 and 16');
  });

  it('accepts a per-page channel in range', () => {
    expect(validateConfig(cfgWith(15)).isValid).toBe(true);
  });

  it('surfaces a bad channel on a NON-active page as a prefixed save-blocker line', () => {
    const cfg = {
      device: 'one1', active_page: 0,
      pages: [
        { name: 'Home', buttons: [{ label: 'B0', cc: 20, color: 'green' }] },
        { name: 'Bad', global_channel: 99, buttons: [{ label: 'B1', cc: 21, color: 'red' }] },
      ],
    } as never;
    const lines = validateAllPages(cfg);
    expect(lines.some(l => l.includes('Page 2 (Bad)') && l.includes('global_channel'))).toBe(true);
  });
});
```

Confirm `validateAllPages` is already imported in the test file; if not, add it to the import.

**Step 2: Run to verify failure**

```bash
cd config-editor && npx vitest run src/lib/validation.test.ts
```
Expected: first + third FAIL; second passes.

**Step 3: Implement**

In `validation.ts` `validatePage`, right after the `page.name` block (`:117-119`):

```ts
  // Per-page MIDI channel override (0-15). Absent = inherit device default.
  if (page.global_channel !== undefined) {
    const chError = validators.channel(page.global_channel);
    if (chError) errors.set('global_channel', chError);
  }
```

**Step 4: Run to verify pass**

```bash
cd config-editor && npx vitest run src/lib/validation.test.ts
```
Expected: PASS.

**Step 5: Commit**

```bash
git add config-editor/src/lib/validation.ts config-editor/src/lib/validation.test.ts
git commit -m "Client-validate per-page global_channel (mirrors Rust 0-15 range)"
```

---

### Task 3: `PageSettingsSection.svelte` — per-page channel UI + normalize strip

A small per-page section rendered **inside** the `{#key currentPage.__uiId}` block so it rebuilds when the active page changes (no stale value bleeding across pages). One number input, 1–16, empty = inherit. Clearing writes `undefined` via `updatePageField`; `normalizeConfig` strips a leftover `global_channel: undefined` key so saved JSON stays clean (same idiom as the `p.name === ''` / empty-`display` strips).

**Files:**
- Create: `config-editor/src/lib/components/PageSettingsSection.svelte`
- Modify: `config-editor/src/routes/+page.svelte` (imports `:17-24`; inside the keyed block `:397-401`)
- Modify: `config-editor/src/lib/formStore.ts` (`normalizeConfig` pages map, `:735-744`)
- Modify: `config-editor/src/lib/formStore.test.ts`

**Step 1: Write the failing store test (normalize strip)**

Append to `formStore.test.ts` (reuse its `makeConfig` helper if present; otherwise build a minimal `one1` config inline):

```ts
it('normalizeConfig drops a per-page global_channel that was cleared to undefined', () => {
  const cfg = {
    device: 'one1', active_page: 0,
    pages: [{ name: 'Home', global_channel: undefined, buttons: [{ label: 'B0', cc: 20, color: 'green' }] }],
  } as never;
  const out = normalizeConfig(cfg);
  expect('global_channel' in out.pages[0]).toBe(false);
});
```

Ensure `normalizeConfig` is imported in the test file.

**Step 2: Run to verify failure**

```bash
cd config-editor && npx vitest run src/lib/formStore.test.ts
```
Expected: FAIL (`structuredClone` keeps the `global_channel: undefined` key).

**Step 3: Implement the strip**

In `formStore.ts` `normalizeConfig`, inside `cloned.pages.map(page => { … })` (after the `p.name === ''` strip, `:740-742`):

```ts
      if (p.global_channel === undefined) {
        delete p.global_channel;
      }
```

**Step 4: Verify the strip test passes**

```bash
cd config-editor && npx vitest run src/lib/formStore.test.ts
```
Expected: PASS.

**Step 5: Create the component**

`config-editor/src/lib/components/PageSettingsSection.svelte`:

```svelte
<script lang="ts">
  import Accordion from './Accordion.svelte';
  import { currentPage, updatePageField, validationErrors } from '$lib/formStore';

  // Display 1-16; stored 0-15. Empty input = inherit the device-wide default.
  let channelValue = $derived(
    $currentPage?.global_channel === undefined ? '' : String($currentPage.global_channel + 1)
  );
  let channelError = $derived($validationErrors.get('global_channel'));

  function handleChannelChange(e: Event) {
    const raw = (e.target as HTMLInputElement).value.trim();
    if (raw === '') {
      updatePageField('global_channel', undefined); // inherit device default
      return;
    }
    const clamped = Math.max(1, Math.min(16, parseInt(raw, 10)));
    updatePageField('global_channel', clamped - 1);
  }
</script>

<Accordion title="Page Settings">
  <div class="field-group">
    <label for="page-global-channel">Page MIDI Channel:</label>
    <input
      id="page-global-channel"
      type="number"
      class="input-number"
      min="1"
      max="16"
      placeholder="Inherit"
      value={channelValue}
      onblur={handleChannelChange}
    />
    <p class="help-text">
      Overrides the device Global MIDI Channel for buttons on this page only.
      Leave blank to inherit the device default. Individual buttons can still override this.
    </p>
    {#if channelError}<p class="error-text">{channelError}</p>{/if}
  </div>
</Accordion>

<style>
  .field-group { display: flex; flex-direction: column; gap: 4px; }
  label { font-size: 13px; font-weight: 600; color: var(--color-text-secondary); }
  .input-number { width: 80px; padding: 5px 8px; font-size: 13px;
    background-color: var(--color-bg); color: var(--color-text);
    border: 1px solid var(--color-border); border-radius: 4px; }
  .help-text { font-size: 12px; color: var(--color-text-secondary); margin: 2px 0 0; }
  .error-text { font-size: 12px; color: var(--error-text, #f48771); margin: 2px 0 0; }
</style>
```

> `DisplaySection.svelte` does **not** use `.field-group`/`.help-text`/`.error-text` (it's built on `.field-row`/`.display-section` instead) — do not copy it for these classes. Match `DeviceSection.svelte` for `.field-group`/`.help-text`, and `EncoderSection.svelte` or `PageControlSection.svelte` for `.error-text`.

**Step 6: Wire into `+page.svelte`**

Add the import alongside the other section imports (`:17-24`):

```svelte
  import PageSettingsSection from '$lib/components/PageSettingsSection.svelte';
```

Render it as the **first** child inside the keyed page-scoped block (`:397-401`), so per-page fields group above Buttons:

```svelte
        {#key $currentPage?.__uiId}
          <PageSettingsSection />
          <ButtonsSection />
          <EncoderSection />
          <ExpressionSection />
        {/key}
```

**Step 7: Verify build + full front-end suite**

```bash
cd config-editor && npm run check && npx vitest run
```
Expected: `svelte-check` clean; all vitest green.

**Step 8: Commit**

```bash
git add config-editor/src/lib/components/PageSettingsSection.svelte \
        config-editor/src/routes/+page.svelte \
        config-editor/src/lib/formStore.ts config-editor/src/lib/formStore.test.ts
git commit -m "Per-page MIDI Channel field: new Page Settings section (updatePageField, empty = inherit)"
```

---

### Task 4: e2e — per-page channel round-trips and is page-scoped

**Files:**
- Create: `config-editor/e2e/page-settings.spec.ts`

**Step 1: Write the spec**

```ts
import { test, expect } from '@playwright/test';
import { loadApp, twoPageConfig, readStoreJson } from './helpers';

test('per-page MIDI channel writes to the active page, blank inherits', async ({ page }) => {
  await loadApp(page, twoPageConfig()); // page 0 = 'A', page 1 = 'B'

  const channel = page.getByLabel('Page MIDI Channel:');
  await channel.fill('10');
  await channel.blur(); // WebKit doesn't blur on click — commit explicitly

  let json = await readStoreJson(page);
  expect(json.pages[0].global_channel).toBe(9); // 10 displayed -> 9 stored

  // Switch to page B: the field must NOT show page A's value.
  await page.getByLabel('Page').selectOption('1');
  await expect(page.getByLabel('Page MIDI Channel:')).toHaveValue('');

  json = await readStoreJson(page);
  expect(json.pages[1].global_channel).toBeUndefined();
});
```

**Step 2: Run**

```bash
cd config-editor && npx playwright test page-settings.spec.ts
```
Expected: PASS. (If the label selector is ambiguous with the device-wide "Global MIDI Channel:", the distinct label text "Page MIDI Channel:" disambiguates — confirm the two labels differ, which they do.)

**Step 3: Commit**

```bash
git add config-editor/e2e/page-settings.spec.ts
git commit -m "e2e: per-page MIDI channel is page-scoped and round-trips (P4d)"
```

---

# Part B — Page templates

### Task 5: Rust `templates.rs` — export a page to a file

New module. `export` deserializes the incoming page into a `Page` (drops `__uiId` and any UI-only fields for free — `Page`/`ButtonConfig` don't declare them), then writes pretty JSON via the existing `write_sync`.

**Files:**
- Create: `config-editor/src-tauri/src/templates.rs`
- Modify: `config-editor/src-tauri/src/lib.rs` (`mod templates;` — full handler registration lands in Task 8)

**Step 1: Write the failing test**

Create `templates.rs` with the test module scaffold first:

```rust
//! Page template import/export (#15 P4d). Templates are host-side JSON files,
//! one `Page` object per file. Import validates the page against the *current*
//! device via `MidiCaptainConfig::validate()` — no silent reshaping (D9).

use crate::commands::{write_sync, ConfigError};
use crate::config::{DeviceType, Page};
use std::fs;
use std::path::Path;

#[derive(Debug, serde::Serialize)]
pub struct TemplateInfo {
    pub name: String, // file stem, e.g. "Lead Tone"
    pub path: String, // absolute path
}

/// Write `page` to `path` as pretty JSON. Overwrites.
pub(crate) fn write_template(path: &Path, page: &Page) -> Result<(), ConfigError> {
    let pretty = serde_json::to_string_pretty(page)?;
    write_sync(path, pretty.as_bytes())?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn a_page() -> Page {
        serde_json::from_value(json!({
            "name": "Lead", "buttons": [{"label": "B0", "cc": 20, "color": "green"}]
        })).unwrap()
    }

    #[test]
    fn write_then_read_back_is_a_valid_page() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("lead.json");
        write_template(&path, &a_page()).unwrap();
        let back: Page = serde_json::from_str(&fs::read_to_string(&path).unwrap()).unwrap();
        assert_eq!(back.name.as_deref(), Some("Lead"));
        assert_eq!(back.buttons.len(), 1);
    }
}
```

Add `mod templates;` to `lib.rs` (below `mod reflash;`).

Confirm `ConfigError` and `write_sync` are reachable as `pub(crate)` from `commands` (they are: `write_sync` is `pub(crate)`, `ConfigError` is `pub`). Confirm `Page`, `DeviceType`, `MidiCaptainConfig` are `pub` in `config` (they are).

**Step 2: Run to verify pass** (this task's helper is pure; the test should pass once it compiles)

```bash
cd config-editor/src-tauri && cargo test --lib write_then_read_back_is_a_valid_page
```
Expected: PASS. (If `Page` fields you reference differ, align with `config.rs:464-477`.)

**Step 3: Commit**

```bash
git add config-editor/src-tauri/src/templates.rs config-editor/src-tauri/src/lib.rs
git commit -m "templates.rs: write_template + module scaffold (P4d)"
```

---

### Task 6: Rust — import a page, checking only device *shape* (D9)

Import rejects a file **only** for reasons the editor can't fix for the target device — the D9 "no silent reshaping" guarantee. Concretely: (a) the file isn't a `Page` at all, (b) wrong button count for the device, (c) an encoder or expression pedal on a non-STD10. Those are structural: there's no editor control to fix them, so a bad import would be a permanently-unsaveable dead end.

Everything else — out-of-range `page_jump` targets, CC/channel/step values, over-long labels — is a **value** problem with a corresponding editor input. Import does **not** check those. The page is inserted, the offending control is flagged by the existing per-field validation (the `page_jump` range check already shipped in P4b), and save stays blocked until the user fixes or deletes it — exactly like any other validation error (user direction, 2026-07-06). This matches D9's literal scope ("button count, capabilities") and lets us drop the whole config-wrapping / sibling-padding / `page_count` machinery.

**Files:**
- Modify: `config-editor/src-tauri/src/templates.rs`

**Step 1: Write the failing tests**

Append to `templates.rs` `mod tests`:

```rust
    fn write_json(dir: &Path, name: &str, v: serde_json::Value) -> std::path::PathBuf {
        let p = dir.join(name);
        fs::write(&p, serde_json::to_string(&v).unwrap()).unwrap();
        p
    }

    #[test]
    fn import_accepts_a_shape_matching_page() {
        let dir = tempfile::tempdir().unwrap();
        let p = write_json(dir.path(), "ok.json",
            json!({ "name": "Lead", "buttons": [{"label": "B0", "cc": 20, "color": "green"}] }));
        let value = read_template(&p, DeviceType::One1).unwrap();
        assert_eq!(value["name"], "Lead");
    }

    #[test]
    fn import_rejects_wrong_button_count_for_device() {
        let dir = tempfile::tempdir().unwrap();
        // A 10-button page (STD10-shaped) imported into a one1 config must reject:
        // one1 renders 1 button row, so 10 buttons can't be fixed in the editor.
        let buttons: Vec<_> = (0..10).map(|i| json!({"label": format!("B{i}"), "color": "green"})).collect();
        let p = write_json(dir.path(), "big.json", json!({ "buttons": buttons }));
        let err = read_template(&p, DeviceType::One1).unwrap_err();
        assert!(err.message.to_lowercase().contains("template"), "got {:?}", err);
    }

    #[test]
    fn import_rejects_encoder_on_non_std10() {
        let dir = tempfile::tempdir().unwrap();
        // Encoder is STD10-only; a one1 has no way to represent or remove it.
        let p = write_json(dir.path(), "enc.json", json!({
            "buttons": [{"label": "B0", "cc": 20, "color": "green"}],
            "encoder": {"enabled": true, "cc": 11, "label": "ENC", "min": 0, "max": 127, "initial": 64}
        }));
        assert!(read_template(&p, DeviceType::One1).is_err());
    }

    #[test]
    fn import_rejects_non_page_json() {
        let dir = tempfile::tempdir().unwrap();
        // A whole-config file (has "pages", no top-level "buttons") is not a Page.
        let p = write_json(dir.path(), "cfg.json", json!({ "device": "one1", "pages": [] }));
        assert!(read_template(&p, DeviceType::One1).is_err());
    }

    #[test]
    fn import_allows_out_of_range_jump_target() {
        let dir = tempfile::tempdir().unwrap();
        // A page_jump to page 9 is a VALUE problem, not a shape one: the page
        // imports fine and the button is flagged in-editor (P4b validation) /
        // blocked at save — NOT rejected at import.
        let p = write_json(dir.path(), "jump.json", json!({
            "buttons": [{"label": "GO", "type": "page_jump", "page": 9, "color": "green"}]
        }));
        assert!(read_template(&p, DeviceType::One1).is_ok());
    }
```

**Step 2: Run to verify failure**

```bash
cd config-editor/src-tauri && cargo test --lib import_
```
Expected: all four FAIL (`read_template` undefined).

**Step 3: Implement**

Add to `templates.rs` (above the test module):

```rust
/// Button count the device expects per page (mirrors the match in
/// `MidiCaptainConfig::validate`). Kept local to avoid widening config.rs's API.
fn expected_button_count(device: DeviceType) -> usize {
    match device {
        DeviceType::Std10 => 10,
        DeviceType::Mini6 => 6,
        DeviceType::Nano4 => 4,
        DeviceType::Duo2 => 2,
        DeviceType::One1 => 1,
    }
}

/// Device-*shape* problems the editor cannot fix for `device` — the only reasons
/// to reject an imported template outright (D9: no silent reshaping). Value
/// problems (out-of-range jump targets, CC/channel/step values, long labels) are
/// deliberately NOT checked here: the page is inserted and those surface as
/// normal in-editor validation errors the user can fix, with save blocked until
/// they do. This mirrors D9's literal scope ("button count, capabilities").
fn device_shape_errors(device: DeviceType, page: &Page) -> Vec<String> {
    let mut errs = Vec::new();
    let expected = expected_button_count(device);
    if page.buttons.len() != expected {
        errs.push(format!(
            "This template has {} buttons; {:?} supports {}.",
            page.buttons.len(), device, expected
        ));
    }
    if device != DeviceType::Std10 {
        if page.encoder.is_some() {
            errs.push(format!("{:?} does not support an encoder.", device));
        }
        if page.expression.is_some() {
            errs.push(format!("{:?} does not support expression pedals.", device));
        }
    }
    errs
}

/// Read a template file, check its shape against `device`, and return the page as
/// a JSON value ready to insert. Value-level problems are left for in-editor
/// validation (see `device_shape_errors`).
pub(crate) fn read_template(path: &Path, device: DeviceType) -> Result<serde_json::Value, ConfigError> {
    let contents = fs::read_to_string(path)?;
    let value: serde_json::Value = serde_json::from_str(&contents)?;

    // Shape guard: must deserialize as a Page (rejects whole-config or junk files).
    let page: Page = serde_json::from_value(value)
        .map_err(|e| ConfigError::msg(format!("Not a valid page template: {e}")))?;

    let shape = device_shape_errors(device, &page);
    if !shape.is_empty() {
        return Err(ConfigError {
            message: "Template is not valid for this device".to_string(),
            details: Some(shape),
        });
    }

    Ok(serde_json::to_value(&page)?)
}
```

> Imports: `read_template` / `device_shape_errors` use `DeviceType`, `Page`, and `std::fs` — all already imported by the Task 5 scaffold. No new top-level `use` needed; `MidiCaptainConfig` is intentionally not imported (unused).

> **DRY note:** `device_shape_errors` mirrors three checks that also live in `validate()`'s per-page loop. They're left duplicated rather than extracted: `validate()`'s versions are entangled with the `Page N, ` prefix and the full-config loop, and a shared helper would need to thread that context. Three one-line checks is below the extraction threshold; revisit only if a fourth shape rule appears.

**Step 4: Run to verify pass**

```bash
cd config-editor/src-tauri && cargo test --lib import_
```
Expected: PASS.

**Step 5: Commit**

```bash
git add config-editor/src-tauri/src/templates.rs
git commit -m "templates.rs: read_template validates imported page vs current device (D9)"
```

---

### Task 7: Rust — list templates in the default folder

Pure, tempdir-testable helper that lists `*.json` files in a directory (creating it if missing), sorted by name. The `AppHandle`-resolving command wrapper lands in Task 8.

**Files:**
- Modify: `config-editor/src-tauri/src/templates.rs`

**Step 1: Write the failing test**

```rust
    #[test]
    fn list_templates_returns_sorted_json_stems() {
        let dir = tempfile::tempdir().unwrap();
        fs::write(dir.path().join("Zebra.json"), "{}").unwrap();
        fs::write(dir.path().join("Alpha.json"), "{}").unwrap();
        fs::write(dir.path().join("notes.txt"), "ignore me").unwrap();
        let list = list_templates_in(dir.path()).unwrap();
        let names: Vec<_> = list.iter().map(|t| t.name.as_str()).collect();
        assert_eq!(names, ["Alpha", "Zebra"]);
    }

    #[test]
    fn list_templates_creates_missing_dir() {
        let dir = tempfile::tempdir().unwrap();
        let sub = dir.path().join("templates");
        assert!(list_templates_in(&sub).unwrap().is_empty());
        assert!(sub.is_dir());
    }
```

**Step 2: Run to verify failure**

```bash
cd config-editor/src-tauri && cargo test --lib list_templates_
```
Expected: FAIL (`list_templates_in` undefined).

**Step 3: Implement**

```rust
/// List `*.json` templates in `dir` (created if absent), sorted by file stem.
pub(crate) fn list_templates_in(dir: &Path) -> Result<Vec<TemplateInfo>, ConfigError> {
    fs::create_dir_all(dir)?;
    let mut out = Vec::new();
    for entry in fs::read_dir(dir)? {
        let entry = entry?;
        let path = entry.path();
        if path.extension().and_then(|e| e.to_str()) == Some("json") {
            if let Some(stem) = path.file_stem().and_then(|s| s.to_str()) {
                out.push(TemplateInfo {
                    name: stem.to_string(),
                    path: path.to_string_lossy().to_string(),
                });
            }
        }
    }
    out.sort_by(|a, b| a.name.cmp(&b.name));
    Ok(out)
}
```

**Step 4: Run to verify pass**

```bash
cd config-editor/src-tauri && cargo test --lib list_templates_
```
Expected: PASS.

**Step 5: Commit**

```bash
git add config-editor/src-tauri/src/templates.rs
git commit -m "templates.rs: list_templates_in (sorted .json stems, creates dir)"
```

---

### Task 8: Tauri commands + handler registration (+ confirm capabilities)

Add the thin `#[command]` wrappers that resolve the default templates dir via `AppHandle`, then register everything in `lib.rs`. **Capabilities need no change** — confirm this empirically rather than editing `capabilities/default.json`.

**Files:**
- Modify: `config-editor/src-tauri/src/templates.rs` (command wrappers)
- Modify: `config-editor/src-tauri/src/lib.rs` (imports + `generate_handler!`)

**Step 1: Add command wrappers to `templates.rs`**

```rust
use tauri::{command, AppHandle, Manager};

/// Absolute path of the default templates folder (`<app_data_dir>/templates`),
/// created on demand. The frontend uses this as the file pickers' default path.
fn templates_dir(app: &AppHandle) -> Result<std::path::PathBuf, ConfigError> {
    let dir = app
        .path()
        .app_data_dir()
        .map_err(|e| ConfigError::msg(format!("Could not resolve app data dir: {e}")))?
        .join("templates");
    fs::create_dir_all(&dir)?;
    Ok(dir)
}

#[command]
pub fn page_templates_dir(app: AppHandle) -> Result<String, ConfigError> {
    Ok(templates_dir(&app)?.to_string_lossy().to_string())
}

#[command]
pub fn export_page_template(path: String, page: Page) -> Result<(), ConfigError> {
    write_template(Path::new(&path), &page)
}

#[command]
pub fn import_page_template(path: String, device: DeviceType) -> Result<serde_json::Value, ConfigError> {
    read_template(Path::new(&path), device)
}

#[command]
pub fn list_page_templates(app: AppHandle) -> Result<Vec<TemplateInfo>, ConfigError> {
    list_templates_in(&templates_dir(&app)?)
}
```

> `DeviceType` must `Deserialize` from the JS device string (it already does — it's used as a command-adjacent type across the config). Custom commands need **no** capability entry in Tauri v2 (the existing `read_config` etc. work with only `core:default`).

**Step 2: Register in `lib.rs`**

Extend the `use commands::…` line with a new templates import and add the four commands to `generate_handler!`:

```rust
use templates::{export_page_template, import_page_template, list_page_templates, page_templates_dir};
```

Add to the `tauri::generate_handler![ … ]` list (after `rpi_rp2_mount_path`):

```rust
            rpi_rp2_mount_path,
            export_page_template,
            import_page_template,
            list_page_templates,
            page_templates_dir
```

**Step 3: Confirm capabilities — do NOT edit unless the check fails**

The design doc (D8) assumed `dialog` save/open scope must be added. In `tauri-plugin-dialog` 2.6.0 the `dialog:default` set already grants `allow-save` and `allow-open`, so `capabilities/default.json` needs no change. Verify:

```bash
cd config-editor/src-tauri
cat "$(find ~/.cargo -path '*tauri-plugin-dialog*/permissions/default.toml' | head -1)"
```
Expected: the `permissions` list includes `allow-save` and `allow-open`. If (and only if) a future plugin version drops them, add `"dialog:allow-save"` and `"dialog:allow-open"` to `capabilities/default.json` and note it in the commit.

**Step 4: Build**

```bash
cd config-editor/src-tauri && cargo build && cargo test --lib
```
Expected: compiles; all templates tests green.

**Step 5: Commit**

```bash
git add config-editor/src-tauri/src/templates.rs config-editor/src-tauri/src/lib.rs
git commit -m "Register page-template commands (export/import/list/dir); dialog:default already grants save+open"
```

---

### Task 9: Frontend `api.ts` wrappers + store insert helper

**Files:**
- Modify: `config-editor/src/lib/api.ts`
- Modify: `config-editor/src/lib/formStore.ts` (new `addPageFromTemplate` + a clean-active-page getter)
- Modify: `config-editor/src/lib/formStore.test.ts`

**Step 1: Write the failing store tests**

Append to `formStore.test.ts` (mirror how existing CRUD tests reset/seed the store — reuse the P4a test helpers):

```ts
describe('addPageFromTemplate (P4d)', () => {
  it('inserts the page after the active page, stamps a fresh __uiId, and switches to it', () => {
    // Seed a 1-page one1 config via the same path the other CRUD tests use.
    loadConfigForTest({ device: 'one1', active_page: 0,
      pages: [{ name: 'Home', buttons: [{ label: 'B0', cc: 20, color: 'green' }] }] });
    addPageFromTemplate({ name: 'Tmpl', buttons: [{ label: 'T0', cc: 30, color: 'red' }] });
    const cfg = get(config);
    expect(cfg.pages).toHaveLength(2);
    expect(cfg.pages[1].name).toBe('Tmpl');
    expect(cfg.active_page).toBe(1);
    expect(typeof (cfg.pages[1] as any).__uiId).toBe('number');
  });

  it('is a no-op at the 20-page cap', () => {
    const pages = Array.from({ length: PAGE_CAP }, (_, i) =>
      ({ name: `P${i}`, buttons: [{ label: 'B', cc: 20, color: 'green' }] }));
    loadConfigForTest({ device: 'one1', active_page: 0, pages });
    addPageFromTemplate({ buttons: [{ label: 'X', cc: 1, color: 'green' }] });
    expect(get(config).pages).toHaveLength(PAGE_CAP);
  });
});
```

> Use whatever seeding helper the existing `formStore.test.ts` CRUD tests use (e.g. a `loadConfig`/`setConfigForTest`). If none exists, seed by calling the store's load path the other tests already call — do not invent a new one.

**Step 2: Run to verify failure**

```bash
cd config-editor && npx vitest run src/lib/formStore.test.ts
```
Expected: FAIL (`addPageFromTemplate` undefined).

**Step 3: Implement the store helper**

In `formStore.ts`, next to `duplicatePage` (`:597-609`):

```ts
// Insert an imported template page after the active page and switch to it.
// The value comes from import_page_template (already device-validated in Rust);
// __uiIds are stripped then re-stamped by _commitConfigMutation, same as duplicate.
export function addPageFromTemplate(page: unknown) {
  _commitConfigMutation(cfg => {
    if (cfg.pages.length >= PAGE_CAP) return false;
    const clone = structuredClone(page) as Page;
    _stripUiIds(clone);
    const at = activePageIndex(cfg) + 1;
    cfg.pages.splice(at, 0, clone);
    cfg.active_page = at;
  });
}

// A __uiId-stripped deep clone of the active page, for export as a template.
export function activePageForExport(): Page {
  const cfg = get(formState).config;
  const clone = structuredClone(cfg.pages[activePageIndex(cfg)]);
  _stripUiIds(clone);
  return clone;
}
```

**Step 4: Verify store tests pass**

```bash
cd config-editor && npx vitest run src/lib/formStore.test.ts
```
Expected: PASS.

**Step 5: Add `api.ts` wrappers**

Append to `config-editor/src/lib/api.ts`:

```ts
import type { Page } from './types';

export interface TemplateInfo { name: string; path: string; }

export async function pageTemplatesDir(): Promise<string> {
  return invoke('page_templates_dir');
}

export async function listPageTemplates(): Promise<TemplateInfo[]> {
  return invoke('list_page_templates');
}

export async function exportPageTemplate(path: string, page: Page): Promise<void> {
  return invoke('export_page_template', { path, page });
}

// Rejects only device-shape mismatches; value problems (jump targets, etc.)
// come in and are flagged by in-editor validation.
export async function importPageTemplate(path: string, device: string): Promise<Page> {
  return invoke('import_page_template', { path, device });
}
```

**Step 6: Build check + commit**

```bash
cd config-editor && npm run check && npx vitest run src/lib/formStore.test.ts
```
Expected: clean + green.

```bash
git add config-editor/src/lib/api.ts config-editor/src/lib/formStore.ts config-editor/src/lib/formStore.test.ts
git commit -m "Template api.ts wrappers + store addPageFromTemplate / activePageForExport"
```

---

### Task 10: EditPagesModal — Save-as-template + Add-from-template UI

Add two actions to the modal footer. **Save as template…** exports the active page via a native save dialog defaulting to the templates folder. **Add from template…** shows the folder's existing templates (from `listPageTemplates`) as a picklist plus a **Browse…** button (native open dialog) for elsewhere; the chosen file is imported (device-validated in Rust) and inserted.

**Files:**
- Modify: `config-editor/src/lib/components/EditPagesModal.svelte`

**Step 1: Implement**

Add to the `<script>`:

```ts
  import { save, open } from '@tauri-apps/plugin-dialog';
  import { message } from '@tauri-apps/plugin-dialog';
  import {
    exportPageTemplate, importPageTemplate, listPageTemplates,
    pageTemplatesDir, type TemplateInfo,
  } from '$lib/api';
  import { activePageForExport, addPageFromTemplate } from '$lib/formStore';

  let picking = $state(false);
  let templates = $state<TemplateInfo[]>([]);

  // `commitPendingEdit` is NOT exported from PageBar.svelte (it's a private
  // helper there) — this modal needs its own copy of the same one-liner so a
  // field mid-edit (e.g. a typed-but-not-yet-blurred channel value) commits
  // before export/insert reads the page.
  function commitPendingEdit() {
    const el = document.activeElement;
    if (el instanceof HTMLElement) el.blur();
  }

  async function saveAsTemplate() {
    commitPendingEdit();
    const page = activePageForExport();
    const dir = await pageTemplatesDir();
    const suggested = (page.name || `Page ${activeIndex + 1}`).replace(/[^\w -]/g, '_');
    const path = await save({
      title: 'Save page as template',
      defaultPath: `${dir}/${suggested}.json`,
      filters: [{ name: 'Page template', extensions: ['json'] }],
    });
    if (!path) return; // user cancelled
    try {
      await exportPageTemplate(path, page);
    } catch (e) {
      await message(String((e as { message?: string })?.message ?? e), { title: 'Export failed', kind: 'error' });
    }
  }

  async function openTemplatePicker() {
    commitPendingEdit();
    templates = await listPageTemplates().catch(() => []);
    picking = true;
  }

  async function addFrom(path: string) {
    picking = false;
    try {
      // Shape-checked in Rust; a bad jump target (or other value) still imports
      // and gets flagged in-editor, so the page always lands.
      const page = await importPageTemplate(path, $config.device);
      addPageFromTemplate(page);
    } catch (e) {
      const err = e as { message?: string; details?: string[] };
      const detail = err?.details?.length ? `\n\n${err.details.join('\n')}` : '';
      await message(`${err?.message ?? e}${detail}`, { title: 'Import failed', kind: 'error' });
    }
  }

  async function browseForTemplate() {
    const dir = await pageTemplatesDir();
    const path = await open({
      title: 'Add page from template',
      defaultPath: dir,
      multiple: false,
      filters: [{ name: 'Page template', extensions: ['json'] }],
    });
    if (typeof path === 'string') await addFrom(path);
  }
```

Add the two buttons to the `.row-actions` group in the footer (after the Duplicate button, before the reorder arrows), plus disable Add at the cap:

```svelte
        <button onclick={saveAsTemplate} title="Save this page as a template">Save as template…</button>
        <button
          onclick={openTemplatePicker}
          disabled={pages.length >= PAGE_CAP}
          title="Add a page from a template"
        >Add from template…</button>
```

Add a lightweight picker panel (below the `.page-list`, before `.modal-footer`), listing existing templates + a Browse option:

```svelte
    {#if picking}
      <div class="template-picker">
        <div class="tp-header">
          <span>Choose a template</span>
          <button class="tp-close" onclick={() => (picking = false)} aria-label="Cancel">✕</button>
        </div>
        {#if templates.length}
          <ul class="tp-list">
            {#each templates as t (t.path)}
              <li><button type="button" onclick={() => addFrom(t.path)}>{t.name}</button></li>
            {/each}
          </ul>
        {:else}
          <p class="tp-empty">No saved templates yet.</p>
        {/if}
        <button class="tp-browse" onclick={browseForTemplate}>Browse…</button>
      </div>
    {/if}
```

Add minimal styles consistent with the modal (reuse `.modal-footer button` conventions; scope new classes under `.template-picker`). Keep it simple; the visual polish target matches the rest of the modal.

**Step 2: Build + full front-end suite**

```bash
cd config-editor && npm run check && npx vitest run
```
Expected: `svelte-check` clean; vitest green.

**Step 3: Commit**

```bash
git add config-editor/src/lib/components/EditPagesModal.svelte
git commit -m "Edit Pages modal: Save-as-template + Add-from-template (list + Browse)"
```

---

### Task 11: e2e — template export + import round-trip through the UI

Extend the IPC mock to answer the dialog + template commands, then drive both flows. The mock stores an "exported" page in memory and serves it back on import, so the round-trip is observable without a real filesystem.

**Files:**
- Modify: `config-editor/e2e/helpers.ts` (mock `plugin:dialog|save`, `plugin:dialog|open`, and the four template commands)
- Create: `config-editor/e2e/page-templates.spec.ts`

**Step 1: Extend the mock in `helpers.ts`**

Inside `loadApp`'s `invoke` switch, before `default:`, add:

```ts
          case 'page_templates_dir': return '/e2e/templates';
          case 'list_page_templates':
            return (window as any).__E2E_TEMPLATES__ ?? [];
          case 'plugin:dialog|save':
            return '/e2e/templates/Exported.json';
          case 'plugin:dialog|open':
            return (window as any).__E2E_OPEN_PATH__ ?? null;
          case 'export_page_template':
            (window as any).__E2E_EXPORTED__ = (args as any).page;
            (window as any).__E2E_TEMPLATES__ = [{ name: 'Exported', path: '/e2e/templates/Exported.json' }];
            return null;
          case 'import_page_template':
            // A test may stage a specific page to "import"; otherwise serve
            // whatever export stored (mimics reading the file back).
            return (window as any).__E2E_IMPORT__
              ?? (window as any).__E2E_EXPORTED__
              ?? { buttons: [{ label: 'T0', cc: 30, color: 'green' }] };
```

Also initialise `(window as any).__E2E_TEMPLATES__ = [];` next to `__E2E_WRITES__`.

**Step 2: Write the spec**

```ts
import { test, expect } from '@playwright/test';
import { loadApp, oneButtonConfig, readStoreJson } from './helpers';

test('export a page then add it back as a template', async ({ page }) => {
  await loadApp(page, oneButtonConfig()); // 1 page

  await page.getByRole('button', { name: 'Edit Pages…' }).click();
  const dialog = page.getByRole('dialog', { name: 'Edit Pages' });

  // Export the active page (mock records it + registers it in the list).
  await dialog.getByRole('button', { name: 'Save as template…' }).click();

  // Add from template -> the picker lists "Exported"; click it.
  await dialog.getByRole('button', { name: 'Add from template…' }).click();
  await dialog.getByRole('button', { name: 'Exported' }).click();
  await dialog.getByRole('button', { name: 'Done' }).click();

  const json = await readStoreJson(page);
  expect(json.pages).toHaveLength(2);
  // Inserted page carries the exported button data.
  expect(json.pages[1].buttons[0].label).toBe('B0');
  expect(json.active_page).toBe(1);
});

test('a template with an out-of-range jump imports and flags the button (not rejected)', async ({ page }) => {
  await loadApp(page, oneButtonConfig()); // 1 page -> only index 0 is valid
  // Stage the "imported" page: its button jumps to page 9, which won't exist.
  await page.evaluate(() => {
    (window as any).__E2E_IMPORT__ = { buttons: [{ label: 'GO', type: 'page_jump', page: 9, color: 'green' }] };
    (window as any).__E2E_TEMPLATES__ = [{ name: 'Jumper', path: '/e2e/templates/Jumper.json' }];
  });

  await page.getByRole('button', { name: 'Edit Pages…' }).click();
  const dialog = page.getByRole('dialog', { name: 'Edit Pages' });
  await dialog.getByRole('button', { name: 'Add from template…' }).click();
  await dialog.getByRole('button', { name: 'Jumper' }).click();
  await dialog.getByRole('button', { name: 'Done' }).click();

  // The page landed (2 pages, newly-added one active) even though the jump is bad.
  const json = await readStoreJson(page);
  expect(json.pages).toHaveLength(2);
  expect(json.active_page).toBe(1);

  // And the bad target is flagged inline like any other validation error
  // (P4b renders the page_jump error near the button's target input).
  await expect(page.locator('.error-text, .error').filter({ hasText: /page/i }).first()).toBeVisible();
});
```

> The final assertion's selector must match however P4b renders the `buttons[i].page` error next to the jump-target input in `ButtonRow.svelte` — confirm the class/text and adjust. The load-bearing part is that the page is present with `active_page: 1`; the flag being visible is the confirmation of the "let it in and flag it" behavior.

**Step 3: Run**

```bash
cd config-editor && npx playwright test page-templates.spec.ts
```
Expected: both tests PASS.

**Step 4: Commit**

```bash
git add config-editor/e2e/helpers.ts config-editor/e2e/page-templates.spec.ts
git commit -m "e2e: page template export -> add-from-template round-trip (P4d)"
```

---

# Part C — Verification & wrap-up

### Task 12: Full suite + manual smoke + PR

**Step 1: Full automated suite**

```bash
cd /Users/maximiliancascone/github/midi-captain-max
./tools/test-all.sh
```
Expected: ALL GREEN. If `test_check_volume_midicaptain` fails, unplug any real MIDI Captain and re-run (session-file note).

```bash
cd config-editor && npx playwright test
```
Expected: all e2e green (prior specs + the two new ones).

**Step 2: Manual smoke** (`npm run tauri dev` in your own terminal — background tasks get killed; session-file note). With a fake-device RAM disk or a real device:

- [ ] **Per-page channel round-trip:** set Page MIDI Channel = 10 on page 1, switch to page 2 (field blank), switch back (still 10). Save; reopen View JSON → `pages[0].global_channel: 9`, `pages[1]` has none.
- [ ] **Blank inherits:** clear the field → View JSON shows no `global_channel` on that page.
- [ ] **Out-of-range blocks save:** (can't type >16 via the clamp; verify a hand-crafted bad value on a non-active page surfaces a footer "Page N: global_channel…" line — exercised by unit tests, spot-check optional.)
- [ ] **Save as template:** Edit Pages → Save as template… → accept default path in the templates folder → file written.
- [ ] **Add from template (list):** Edit Pages → Add from template… → the just-saved template appears → click → new page inserted after the active one, selected.
- [ ] **Add from template (Browse):** Browse… → pick the file elsewhere → inserted.
- [ ] **Shape-mismatch reject:** save a template from an STD10 config, switch to a ONE device (or open a ONE config), Add from template… that file → import rejected with a "not valid for this device" message (wrong button count / encoder); no page added.
- [ ] **Out-of-range jump imports and is flagged:** import a template whose button jumps to a page beyond the current count → the page IS added and selected, the jump button shows a validation error, and Save is blocked until it's fixed or the page deleted (not rejected at import).
- [ ] **Cap:** at 20 pages, "Add from template…" is disabled.

**Step 3: Update session file**

Update `~/.claude/session-midi-captain-max-15-pages-p4.md` (or a P4d-specific session file) with what shipped, verification state, and mark #15 P4 complete pending merge.

**Step 4: Open the PR** (only on the user's go-ahead — see memory `feedback_batch_prs`)

- Problem section leads with the symptom / user-visible gap (no way to reuse a page across configs; no per-page channel); Root cause / mechanism under a separate heading (memory `feedback_problem_statements`).
- Record the verified passing suite counts (memory `feedback_pr_test_recording`).
- Note the design-doc correction: `dialog:default` already grants save/open, so no capabilities widening was needed (the D8 assumption was stale).

```bash
git push -u origin 15-pages-p4d
gh pr create --title "…" --body "…"
```

---

## Notes / decisions baked into this plan

- **Design-doc correction (D8):** `capabilities/default.json` is **not** modified — `tauri-plugin-dialog` 2.6.0's `dialog:default` already includes `allow-save` + `allow-open` (verified in `~/.cargo/.../permissions/default.toml`). Task 8 keeps a guard that only edits capabilities if a future version drops them.
- **No JS `fs` capability:** template read/write is Rust `std::fs` inside the commands, which bypasses the JS ACL entirely. Only the dialog pickers touch JS scope.
- **Import validation (D9)** checks device *shape* only — button count and encoder/expression capability — because those are the only problems the editor can't fix for the target device. Everything else (out-of-range `page_jump` targets, CC/channel/step values, long labels) is a fixable value error: the page imports, the offending control is flagged by the existing in-editor validation, and save is blocked until it's fixed (user direction, 2026-07-06). This matches D9's literal scope ("button count, capabilities") and drops the earlier config-wrapping / `page_count` machinery.
- **`page_templates_dir` is a 4th command** beyond D8's three, added because the file pickers need a `defaultPath` to "default to the common templates folder." Small and justified; noted here so it isn't mistaken for scope creep.
- **Per-page `global_channel`** uses the D6 `updatePageField` seam and renders inside the existing `{#key currentPage.__uiId}` block so per-page state can't leak across pages. Empty input writes `undefined`; `normalizeConfig` strips it (matches the `name`/`display` idioms).
- **Out of scope (unchanged):** per-page `display` overrides and the D10 font-reload RAM probe (wait for the display/fonts rewrite — session file, 2026-07-06); whole-config templates (D7).
