<script lang="ts">
  import KeytimesMessageEditor from './KeytimesMessageEditor.svelte';
  import type { ButtonConfig, KeytimesEntry, CycleEntryColor } from '$lib/types';
  import { BUTTON_COLORS } from '$lib/types';
  import {
    addKeytimesEntry,
    removeKeytimesEntry,
    addKeytimesMessage,
    updateField,
    validationErrors,
  } from '$lib/formStore';

  interface Props {
    button: ButtonConfig;
    index: number;
    globalChannel: number;
  }

  let { button, index, globalChannel }: Props = $props();

  // Color palette for cycle entries: standard button colors plus "off".
  const CYCLE_COLORS: CycleEntryColor[] = [
    'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'white', 'off',
  ];

  // Per-entry color picker: shows current value, swatch, and clear-to-inherit option.
  function setEntryColor(cycle: 'short' | 'long', entryIndex: number, color: CycleEntryColor | undefined) {
    updateField(`buttons[${index}].${cycle}[${entryIndex}].color`, color);
  }

  function setEntryDim(cycle: 'short' | 'long', entryIndex: number, dim: boolean) {
    updateField(`buttons[${index}].${cycle}[${entryIndex}].dim`, dim ? true : undefined);
  }

  function setEntryLabel(cycle: 'short' | 'long', entryIndex: number, label: string) {
    updateField(`buttons[${index}].${cycle}[${entryIndex}].label`, label === '' ? undefined : label);
  }

  function handleThresholdChange(e: Event) {
    const target = e.target as HTMLInputElement;
    if (target.value === '') {
      updateField(`buttons[${index}].long_press_threshold_ms`, undefined);
    } else {
      updateField(`buttons[${index}].long_press_threshold_ms`, parseInt(target.value));
    }
  }

  function handleLongOverlayChange(e: Event) {
    const target = e.target as HTMLInputElement;
    updateField(`buttons[${index}].long_overlay`, target.checked ? true : undefined);
  }

  let thresholdError = $derived($validationErrors.get(`buttons[${index}].long_press_threshold_ms`));
</script>

<div class="keytimes-editor">
  <div class="kt-threshold-row">
    <label class="inline">
      Long-press threshold (ms):
      <input type="number" min="50" max="5000"
             value={button.long_press_threshold_ms ?? ''}
             placeholder="500 (global default)"
             oninput={handleThresholdChange}
             class:error={!!thresholdError}
             title="Optional per-button override. Falls back to global long_press_threshold_ms (default 500ms)." />
    </label>
    {#if thresholdError}
      <span class="kt-error">{thresholdError}</span>
    {/if}
  </div>

  <div class="kt-overlay-row">
    <label class="inline"
           title="When set, the long-press color is used instead of the short-press color. Short presses send their messages as expected.">
      <input type="checkbox"
             checked={button.long_overlay ?? false}
             onchange={handleLongOverlayChange} />
      Long-press color overrides short-press color
    </label>
  </div>

  {#each ['short', 'long'] as cycle (cycle)}
    {@const entries = (cycle === 'short' ? button.short : button.long) ?? []}
    <section class="kt-cycle">
      <header class="kt-cycle-header">
        <h4>{cycle === 'short' ? 'Short Press Cycle' : 'Long Press Cycle'}</h4>
        <span class="kt-cycle-hint">
          {#if cycle === 'short'}
            Cycles on every short tap. <code>short_down</code> fires on press, <code>short_up</code> fires on quick release (before threshold).
          {:else}
            Cycles on every long hold. <code>long_down</code> fires when threshold elapses; <code>long_up</code> fires on release after threshold.
          {/if}
        </span>
        <button type="button" class="kt-add" onclick={() => addKeytimesEntry(index, cycle as 'short' | 'long')}>
          + Add entry
        </button>
      </header>

      {#if entries.length === 0}
        <p class="kt-empty">(no entries — button is silent for {cycle} press events)</p>
      {/if}

      {#each entries as entry, ei ((entry as { __uiId?: number }).__uiId ?? ei)}
        <div class="kt-entry">
          <div class="kt-entry-header">
            <span class="kt-entry-num">#{ei + 1}</span>
            <label class="inline">
              Color:
              <select value={entry.color ?? ''}
                      onchange={(e) => setEntryColor(cycle as 'short' | 'long', ei, (e.target as HTMLSelectElement).value === '' ? undefined : (e.target as HTMLSelectElement).value as CycleEntryColor)}>
                <option value="">(inherit)</option>
                {#each CYCLE_COLORS as c}
                  <option value={c}>{c}</option>
                {/each}
              </select>
              {#if entry.color && entry.color !== 'off'}
                <span class="color-swatch" style="background: {BUTTON_COLORS[entry.color as keyof typeof BUTTON_COLORS]}"></span>
              {:else if entry.color === 'off'}
                <span class="color-swatch off" title="LED dark">⌀</span>
              {/if}
            </label>
            <label class="inline">
              <input type="checkbox"
                     checked={entry.dim ?? false}
                     onchange={(e) => setEntryDim(cycle as 'short' | 'long', ei, (e.target as HTMLInputElement).checked)} />
              dim
            </label>
            <label class="inline">
              Label:
              <input type="text" maxlength="6"
                     value={entry.label ?? ''}
                     placeholder="(inherit)"
                     oninput={(e) => setEntryLabel(cycle as 'short' | 'long', ei, (e.target as HTMLInputElement).value)} />
            </label>
            <button type="button" class="kt-remove-entry"
                    onclick={() => removeKeytimesEntry(index, cycle as 'short' | 'long', ei)}
                    title="Remove this entry">
              Remove entry
            </button>
          </div>

          {#each ['down', 'up'] as slot (slot)}
            {@const messages = (slot === 'down' ? entry.down : entry.up) ?? []}
            <div class="kt-slot">
              <div class="kt-slot-header"
                   title="An empty slot does nothing on this event — no MIDI fires and the LED color/label/dim do not update. Add at least one message to make this event take effect.">
                <span class="kt-slot-label">{cycle}_{slot}:</span>
                <button type="button" class="kt-add-msg"
                        onclick={() => addKeytimesMessage(index, cycle as 'short' | 'long', ei, slot as 'down' | 'up')}>
                  + message
                </button>
                {#if messages.length === 0}
                  <span class="kt-slot-empty-hint">(empty — this event fires nothing)</span>
                {/if}
              </div>
              {#each messages as msg, mi ((msg as { __uiId?: number }).__uiId ?? mi)}
                <KeytimesMessageEditor
                  buttonIndex={index}
                  cycle={cycle as 'short' | 'long'}
                  entryIndex={ei}
                  slot={slot as 'down' | 'up'}
                  msgIndex={mi}
                  message={msg}
                  globalChannel={globalChannel}
                />
              {/each}
            </div>
          {/each}
        </div>
      {/each}
    </section>
  {/each}
</div>

<style>
  .keytimes-editor {
    margin-top: 0.75rem;
    padding: 0.75rem;
    background: #f8f9fa;
    border: 1px solid #ccd;
    border-radius: 4px;
  }

  .kt-threshold-row {
    margin-bottom: 0.75rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .kt-cycle {
    margin-top: 0.75rem;
    padding: 0.5rem;
    background: white;
    border: 1px solid #d0d6e0;
    border-radius: 4px;
  }

  .kt-cycle-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 0.5rem;
    flex-wrap: wrap;
  }

  .kt-cycle-header h4 {
    margin: 0;
    font-size: 0.95rem;
    color: #234;
  }

  .kt-cycle-hint {
    font-size: 0.75rem;
    color: #666;
    flex: 1 1 auto;
    min-width: 200px;
  }

  .kt-cycle-hint code {
    background: #eee;
    padding: 0 0.25rem;
    border-radius: 2px;
    font-family: monospace;
  }

  .kt-add {
    padding: 0.25rem 0.5rem;
    background: #e4f0ff;
    border: 1px solid #6aa;
    border-radius: 3px;
    cursor: pointer;
    font-size: 0.8125rem;
  }

  .kt-add:hover {
    background: #d4e8ff;
  }

  .kt-empty {
    margin: 0.5rem 0;
    color: #888;
    font-style: italic;
    font-size: 0.8125rem;
  }

  .kt-entry {
    margin: 0.5rem 0;
    padding: 0.5rem;
    background: #fafbfd;
    border: 1px solid #d8dde5;
    border-radius: 3px;
  }

  .kt-entry-header {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
  }

  .kt-entry-num {
    font-weight: bold;
    color: #456;
  }

  .kt-slot {
    margin: 0.25rem 0 0.25rem 0.5rem;
    padding: 0.25rem;
    border-left: 2px solid #cde;
    padding-left: 0.5rem;
  }

  .kt-slot-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.25rem;
  }

  .kt-slot-label {
    font-family: monospace;
    font-size: 0.8125rem;
    color: #555;
  }

  .kt-slot-empty-hint {
    font-size: 0.75rem;
    color: #999;
    font-style: italic;
  }

  .kt-add-msg {
    padding: 0.125rem 0.4rem;
    background: #f0f0f0;
    border: 1px solid #bbb;
    border-radius: 3px;
    cursor: pointer;
    font-size: 0.75rem;
  }

  .kt-add-msg:hover {
    background: #e0e0e0;
  }

  .kt-remove-entry {
    margin-left: auto;
    padding: 0.125rem 0.5rem;
    background: #fee;
    border: 1px solid #d99;
    color: #c00;
    border-radius: 3px;
    cursor: pointer;
    font-size: 0.75rem;
  }

  .kt-remove-entry:hover {
    background: #fdd;
  }

  label.inline {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    font-size: 0.8125rem;
  }

  input[type="number"], input[type="text"], select {
    padding: 0.125rem 0.25rem;
    border: 1px solid #bbb;
    border-radius: 3px;
    font-size: 0.8125rem;
  }

  input[type="number"] { width: 5rem; }
  input[type="text"] { width: 5rem; }

  input.error {
    border-color: #c00;
    background: #fef0f0;
  }

  .kt-error {
    color: #c00;
    font-size: 0.75rem;
  }

  .color-swatch {
    display: inline-block;
    width: 14px;
    height: 14px;
    border-radius: 50%;
    border: 1px solid #666;
    vertical-align: middle;
  }

  .color-swatch.off {
    background: #222;
    color: #888;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 11px;
  }
</style>
