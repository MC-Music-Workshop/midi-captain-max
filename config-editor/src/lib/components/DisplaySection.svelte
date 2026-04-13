<script lang="ts">
  import Accordion from './Accordion.svelte';
  import { config, updateField, DEVICE_HAS_TFT } from '$lib/formStore';

  let deviceType = $derived($config.device);
  let display = $derived($config.display);
  let isDisabled = $derived(!DEVICE_HAS_TFT[deviceType ?? 'std10']);
  let message = $derived(isDisabled ? `Not available on ${(deviceType ?? '').toUpperCase()}` : undefined);

  function handleField(path: string, e: Event) {
    const target = e.target as HTMLSelectElement;
    updateField(`display.${path}`, target.value);
  }
</script>

<Accordion title="Display Settings" defaultOpen={!isDisabled} disabled={isDisabled} {message}>
  <div class="display-section">
    <div class="field-row">
      <label for="display-button-text-size">Button text size:</label>
      <select
        id="display-button-text-size"
        value={display?.button_text_size ?? 'medium'}
        onchange={(e) => handleField('button_text_size', e)}
      >
        <option value="small">Small</option>
        <option value="medium">Medium</option>
        <option value="large">Large</option>
      </select>
    </div>

    <div class="field-row">
      <label for="display-status-text-size">Status text size:</label>
      <select
        id="display-status-text-size"
        value={display?.status_text_size ?? 'medium'}
        onchange={(e) => handleField('status_text_size', e)}
      >
        <option value="small">Small</option>
        <option value="medium">Medium</option>
        <option value="large">Large</option>
      </select>
    </div>

    <div class="field-row">
      <label for="display-expression-text-size">Expression text size:</label>
      <select
        id="display-expression-text-size"
        value={display?.expression_text_size ?? 'medium'}
        onchange={(e) => handleField('expression_text_size', e)}
      >
        <option value="small">Small</option>
        <option value="medium">Medium</option>
        <option value="large">Large</option>
      </select>
    </div>
  </div>
</Accordion>

<style>
  .display-section {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }
  
  .field-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  
  .field-row label {
    min-width: 160px;
    font-size: 0.875rem;
  }
  
  .field-row select {
    padding: 0.375rem 0.5rem;
    border: 1px solid #ccc;
    border-radius: 4px;
    font-size: 0.875rem;
    background: white;
    min-width: 120px;
  }
</style>
