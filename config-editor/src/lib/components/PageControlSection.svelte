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
