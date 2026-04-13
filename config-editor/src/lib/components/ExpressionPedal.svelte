<script lang="ts">
  import type { ExpressionConfig } from '$lib/types';
  import { config } from '$lib/formStore';
  
  interface Props {
    pedal: ExpressionConfig;
    name: string;
    onUpdate: (field: string, value: any) => void;
  }
  
  let { pedal, name, onUpdate }: Props = $props();
  
  let globalChannel = $derived($config.global_channel ?? 0);
  
  function handleCheckbox(e: Event) {
    const target = e.target as HTMLInputElement;
    onUpdate('enabled', target.checked);
  }
  
  function handleNumberInput(field: string, e: Event) {
    const target = e.target as HTMLInputElement;
    const value = target.value === '' ? undefined : parseInt(target.value, 10);
    onUpdate(field, value);
  }
  
  function handleChannelChange(e: Event) {
    const target = e.target as HTMLInputElement;
    if (target.value === '') {
      onUpdate('channel', undefined);
    } else {
      const value = parseInt(target.value);
      // Convert from 1-16 display to 0-15 storage
      onUpdate('channel', value - 1);
    }
  }
  
  function handleSelect(field: string, e: Event) {
    const target = e.target as HTMLSelectElement;
    onUpdate(field, target.value);
  }
  
  // Display channel as 1-16 (stored as 0-15)
  let displayChannel = $derived(
    pedal.channel !== undefined ? pedal.channel + 1 : undefined
  );
  let effectiveChannel = $derived(
    pedal.channel !== undefined ? pedal.channel + 1 : globalChannel + 1
  );
</script>

<div class="pedal-config">
  <div class="pedal-header">
    <label class="pedal-name">
      <input 
        type="checkbox" 
        checked={pedal.enabled}
        onchange={handleCheckbox}
      />
      <span>{name}</span>
    </label>
  </div>
  
  {#if pedal.enabled}
    <div class="pedal-fields">
      <div class="field-row">
        <label>
          <span class="field-label">Label:</span>
          <input 
            type="text" 
            value={pedal.label}
            maxlength="6"
            onblur={(e) => onUpdate('label', (e.target as HTMLInputElement).value)}
          />
        </label>

        <label>
          <span class="field-label">Channel:</span>
          <input 
            type="number" 
            value={displayChannel !== undefined ? displayChannel : ''}
            min="1"
            max="16"
            placeholder={effectiveChannel.toString()}
            title={pedal.channel !== undefined ? `MIDI Ch ${effectiveChannel}` : `Using global: ${effectiveChannel}`}
            onblur={handleChannelChange}
          />
        </label>

        <label>
          <span class="field-label">CC:</span>
          <input 
            type="number" 
            value={pedal.cc}
            min="0"
            max="127"
            onblur={(e) => handleNumberInput('cc', e)}
          />
        </label>
        
        <label>
          <span class="field-label">Polarity:</span>
          <select 
            value={pedal.polarity || 'normal'}
            onchange={(e) => handleSelect('polarity', e)}
          >
            <option value="normal">Normal</option>
            <option value="inverted">Inverted</option>
          </select>
        </label>
      </div>
      
      <div class="field-row">
        <label>
          <span class="field-label">Min:</span>
          <input 
            type="number" 
            value={pedal.min ?? 0}
            min="0"
            max="127"
            placeholder="0"
            onblur={(e) => handleNumberInput('min', e)}
          />
        </label>
        
        <label>
          <span class="field-label">Max:</span>
          <input 
            type="number" 
            value={pedal.max ?? 127}
            min="0"
            max="127"
            placeholder="127"
            onblur={(e) => handleNumberInput('max', e)}
          />
        </label>
        
        <label>
          <span class="field-label">Threshold:</span>
          <input 
            type="number" 
            value={pedal.threshold ?? 5}
            min="0"
            max="127"
            placeholder="5"
            onblur={(e) => handleNumberInput('threshold', e)}
          />
        </label>
      </div>
    </div>
  {/if}
</div>

<style>
  .pedal-config {
    border: 1px solid var(--border-color, #ddd);
    border-radius: 4px;
    padding: 1rem;
    background: var(--bg-secondary, #fafafa);
  }
  
  .pedal-header {
    margin-bottom: 0.75rem;
  }
  
  .pedal-name {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-weight: 600;
    font-size: 0.95rem;
    cursor: pointer;
  }
  
  .pedal-name input[type="checkbox"] {
    cursor: pointer;
  }
  
  .pedal-fields {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    margin-top: 0.75rem;
    padding-left: 1.5rem;
  }
  
  .field-row {
    display: flex;
    gap: 1rem;
    flex-wrap: wrap;
  }
  
  .field-row label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  
  .field-label {
    font-size: 0.875rem;
    color: var(--text-secondary, #666);
    min-width: 4rem;
  }
  
  input[type="text"],
  input[type="number"],
  select {
    padding: 0.375rem 0.5rem;
    border: 1px solid var(--border-color, #ccc);
    border-radius: 3px;
    font-size: 0.875rem;
    font-family: inherit;
  }
  
  input[type="text"] {
    width: 6rem;
  }
  
  input[type="number"] {
    width: 4.5rem;
  }
  
  select {
    padding: 0.375rem 0.5rem;
    cursor: pointer;
  }
  
  input:focus,
  select:focus {
    outline: 2px solid var(--accent-color, #007aff);
    outline-offset: 1px;
  }
  
  input:disabled,
  select:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
</style>
