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
    const parsed = parseInt(raw, 10);
    if (Number.isNaN(parsed)) return; // garbage input (e.g. a lone "-"); leave the stored value alone
    const clamped = Math.max(1, Math.min(16, parsed));
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
  .field-group { display: flex; flex-direction: column; gap: 0.5rem; }
  label { font-weight: 500; }
  .input-number {
    width: 80px;
    padding: 0.5rem;
    border: 1px solid var(--border-color, #ccc);
    border-radius: 4px;
    font-size: 0.875rem;
    background: var(--bg-primary, white);
    color: var(--text-primary, inherit);
  }
  .help-text { font-size: 0.875rem; color: var(--text-secondary, #666); margin: 0; }
  .error-text { display: block; font-size: 0.75rem; color: #dc3545; margin-top: 2px; }
</style>
