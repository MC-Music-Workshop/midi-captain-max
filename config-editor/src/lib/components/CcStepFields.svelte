<script lang="ts">
  // Button-level fields for cc_inc / cc_dec (#11): the shared CC number, STEP vs
  // SLOT mode, value range, wrap, initial value, and (SLOT mode) the per-slot
  // color/name table. Rendered inline in ButtonRow for a plain cc_inc/cc_dec
  // button, and once per keytimes button whose entries fire cc_inc/cc_dec —
  // the entries only pick a direction, these fields are shared by all of them.
  import ColorSelect from './ColorSelect.svelte';
  import type { ButtonConfig, ButtonColor } from '$lib/types';
  import { validationErrors } from '$lib/formStore';
  import { CC_SLOTS_MIN, CC_SLOTS_MAX } from '$lib/validation';

  interface Props {
    button: ButtonConfig;
    index: number;
    disabled?: boolean;
    onUpdate: (field: string, value: any) => void;
  }

  let { button, index, disabled = false, onUpdate }: Props = $props();

  let basePath = $derived(`buttons[${index}]`);
  const fieldId = (field: string) => `btn-${index}-ccstep-${field}`;

  // cc_slots present = SLOT mode; absent = STEP mode (the firmware keys off the same thing).
  let slotMode = $derived(button.cc_slots !== undefined);
  let slots = $derived(button.cc_slots ?? 4);
  let lo = $derived(button.cc_min ?? 0);
  let hi = $derived(button.cc_max ?? 127);

  // Middle value of each slot — the CC value the firmware actually sends for it
  // (same integer math as core/cc_step.py slot_value()).
  let slotValues = $derived.by(() => {
    const span = hi - lo + 1;
    return Array.from({ length: slots }, (_, i) => lo + Math.floor(((2 * i + 1) * span) / (2 * slots)));
  });

  function err(field: string): string | undefined {
    return $validationErrors.get(`${basePath}.${field}`);
  }

  function intOrUndef(e: Event): number | undefined {
    const v = (e.target as HTMLInputElement).value;
    return v === '' ? undefined : parseInt(v);
  }

  function handleInt(field: string, e: Event) {
    onUpdate(field, intOrUndef(e));
  }

  // Slot tables are kept exactly `n` long so every slot has a color (schema
  // arrays can't hold gaps); names default to '' (falls back to "<label> n/N").
  function resizeTables(n: number) {
    const colors = (button.cc_slot_colors ?? []).slice(0, n);
    while (colors.length < n) colors.push(button.color);
    onUpdate('cc_slot_colors', colors);
    const names = (button.cc_slot_names ?? []).slice(0, n);
    while (names.length < n) names.push('');
    onUpdate('cc_slot_names', names);
  }

  function handleModeChange(e: Event) {
    const mode = (e.target as HTMLInputElement).value;
    if (mode === 'slots') {
      const n = button.cc_slots ?? 4;
      onUpdate('cc_slots', n);
      resizeTables(n);
    } else {
      onUpdate('cc_slots', undefined);
    }
  }

  function handleSlotsChange(e: Event) {
    const raw = intOrUndef(e);
    if (raw === undefined) return;
    onUpdate('cc_slots', raw);
    // Only resize the tables for a legal count; an out-of-range value shows its error.
    if (raw >= CC_SLOTS_MIN && raw <= CC_SLOTS_MAX) resizeTables(raw);
  }

  function handleWrapChange(e: Event) {
    // Default is true; only persist the non-default.
    onUpdate('cc_wrap', (e.target as HTMLInputElement).checked ? undefined : false);
  }

  function handleSlotColor(si: number, color: ButtonColor) {
    const colors = (button.cc_slot_colors ?? []).slice(0, slots);
    while (colors.length < slots) colors.push(button.color);
    colors[si] = color;
    onUpdate('cc_slot_colors', colors);
  }

  function handleSlotName(si: number, e: Event) {
    const names = (button.cc_slot_names ?? []).slice(0, slots);
    while (names.length < slots) names.push('');
    names[si] = (e.target as HTMLInputElement).value;
    onUpdate('cc_slot_names', names);
  }
</script>

<div class="field">
  <label class="field-label" for={fieldId('cc')}>CC:</label>
  <input id={fieldId('cc')} type="number" class="input-num" class:error={!!err('cc')}
    value={button.cc ?? ''} onblur={(e) => handleInt('cc', e)} disabled={disabled}
    min="0" max="127" placeholder={String(20 + index)}
    title="CC number of the shared value. Every CC+/CC- button on any page with this CC and channel moves the same value." />
  {#if err('cc')}<span class="error-text">{err('cc')}</span>{/if}
</div>

<div class="field">
  <span class="field-label">Value mode:</span>
  <div class="radio-row">
    <label class="radio">
      <input type="radio" name={fieldId('mode')} value="step" checked={!slotMode}
        onchange={handleModeChange} disabled={disabled} />
      Step
    </label>
    <label class="radio">
      <input type="radio" name={fieldId('mode')} value="slots" checked={slotMode}
        onchange={handleModeChange} disabled={disabled} />
      Slots
    </label>
  </div>
</div>

{#if slotMode}
  <div class="field">
    <label class="field-label" for={fieldId('slots')}>Slots:</label>
    <input id={fieldId('slots')} type="number" class="input-num" class:error={!!err('cc_slots')}
      value={button.cc_slots} onblur={handleSlotsChange} disabled={disabled}
      min={CC_SLOTS_MIN} max={CC_SLOTS_MAX}
      title="Min..max is split into this many equal slots; each press moves one slot and sends the value in the middle of it." />
    {#if err('cc_slots')}<span class="error-text">{err('cc_slots')}</span>{/if}
  </div>
{:else}
  <div class="field">
    <label class="field-label" for={fieldId('step')}>Step:</label>
    <input id={fieldId('step')} type="number" class="input-num" class:error={!!err('cc_step')}
      value={button.cc_step ?? ''} onblur={(e) => handleInt('cc_step', e)} disabled={disabled}
      min="1" max="127" placeholder="1" title="How much the value moves per press." />
    {#if err('cc_step')}<span class="error-text">{err('cc_step')}</span>{/if}
  </div>
  <div class="field">
    <label class="field-label" for={fieldId('flash-ms')}>Flash (ms):</label>
    <input id={fieldId('flash-ms')} type="number" class="input-num" class:error={!!err('flash_ms')}
      value={button.flash_ms ?? ''} onblur={(e) => handleInt('flash_ms', e)} disabled={disabled}
      min="50" max="5000" step="50" placeholder="200" title="LED flash on each press." />
    {#if err('flash_ms')}<span class="error-text">{err('flash_ms')}</span>{/if}
  </div>
{/if}

<div class="field">
  <label class="field-label" for={fieldId('min')}>Min:</label>
  <input id={fieldId('min')} type="number" class="input-num" class:error={!!err('cc_min')}
    value={button.cc_min ?? ''} onblur={(e) => handleInt('cc_min', e)} disabled={disabled}
    min="0" max="127" placeholder="0" />
  {#if err('cc_min')}<span class="error-text">{err('cc_min')}</span>{/if}
</div>

<div class="field">
  <label class="field-label" for={fieldId('max')}>Max:</label>
  <input id={fieldId('max')} type="number" class="input-num" class:error={!!err('cc_max')}
    value={button.cc_max ?? ''} onblur={(e) => handleInt('cc_max', e)} disabled={disabled}
    min="0" max="127" placeholder="127" />
  {#if err('cc_max')}<span class="error-text">{err('cc_max')}</span>{/if}
</div>

<div class="field">
  <label class="field-label" for={fieldId('initial')}>Initial:</label>
  <input id={fieldId('initial')} type="number" class="input-num" class:error={!!err('cc_initial')}
    value={button.cc_initial ?? ''} onblur={(e) => handleInt('cc_initial', e)} disabled={disabled}
    min={lo} max={hi} placeholder={String(lo)} title="Value at boot, before any press or incoming CC. Default: min." />
  {#if err('cc_initial')}<span class="error-text">{err('cc_initial')}</span>{/if}
</div>

<div class="field">
  <label class="field-label" for={fieldId('wrap')}>Wrap:</label>
  <input id={fieldId('wrap')} type="checkbox" class="checkbox"
    checked={button.cc_wrap ?? true} onchange={handleWrapChange} disabled={disabled}
    title="On: stepping past max lands on min (and below min lands on max). Off: the value stops at the bound." />
</div>

{#if slotMode}
  <div class="slot-table">
    <span class="slot-table-label">Slots (LED color / name):</span>
    {#each slotValues as value, si}
      <div class="slot-row">
        <span class="slot-num">#{si + 1}</span>
        <ColorSelect
          value={button.cc_slot_colors?.[si] ?? button.color}
          onchange={(c) => handleSlotColor(si, c)} />
        <label class="visually-hidden" for={fieldId(`name-${si}`)}>Slot {si + 1} name</label>
        <input id={fieldId(`name-${si}`)} type="text" class="input-name"
          class:error={!!err(`cc_slot_names[${si}]`)}
          value={button.cc_slot_names?.[si] ?? ''} oninput={(e) => handleSlotName(si, e)}
          disabled={disabled} maxlength="6" placeholder="{button.label || 'slot'} {si + 1}/{slots}" />
        <span class="hint-text">sends {value}</span>
        {#if err(`cc_slot_names[${si}]`)}<span class="error-text">{err(`cc_slot_names[${si}]`)}</span>{/if}
      </div>
    {/each}
  </div>
{/if}

<style>
  /* Mirrors ButtonRow's .field look so these render as siblings in its flex row. */
  .field {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    flex-direction: column;
    position: relative;
  }

  .field-label {
    font-size: 0.75rem;
    color: #666;
    align-self: flex-start;
  }

  .input-num {
    width: 60px;
    padding: 0.375rem 0.5rem;
    border: 1px solid #ccc;
    border-radius: 4px;
    font-size: 0.875rem;
  }

  .input-name {
    width: 80px;
    padding: 0.25rem 0.5rem;
    border: 1px solid #ccc;
    border-radius: 4px;
    font-size: 0.875rem;
  }

  .checkbox {
    margin-top: 0.5rem;
  }

  .radio-row {
    display: flex;
    gap: 0.5rem;
    padding-top: 0.25rem;
  }

  .radio {
    display: flex;
    align-items: center;
    gap: 0.2rem;
    font-size: 0.8125rem;
  }

  input.error {
    border-color: #c00;
    background: #fef0f0;
  }

  .error-text {
    font-size: 0.6875rem;
    color: #c00;
    white-space: nowrap;
  }

  .hint-text {
    font-size: 0.6875rem;
    color: #666;
    white-space: nowrap;
  }

  .visually-hidden {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
  }

  .slot-table {
    flex-basis: 100%;
    margin-top: 0.25rem;
    padding: 0.5rem;
    border-top: 1px dashed #e0e0e0;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .slot-table-label {
    font-size: 0.75rem;
    font-weight: 600;
    color: #555;
  }

  .slot-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.25rem 0.5rem;
    background: #fafafa;
    border: 1px solid #eee;
    border-radius: 4px;
  }

  .slot-num {
    font-size: 0.75rem;
    color: #666;
    min-width: 1.75rem;
  }
</style>
