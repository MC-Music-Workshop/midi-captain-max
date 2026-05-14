<script lang="ts">
  import Accordion from './Accordion.svelte';
  import { config, updateField } from '$lib/formStore';

  let thruUsb = $derived($config.midi_thru_usb ?? true);
  let thruDin = $derived($config.midi_thru_din ?? true);

  function handleThruUsbChange(e: Event) {
    const target = e.target as HTMLInputElement;
    updateField('midi_thru_usb', target.checked);
  }

  function handleThruDinChange(e: Event) {
    const target = e.target as HTMLInputElement;
    updateField('midi_thru_din', target.checked);
  }
</script>

<Accordion title="MIDI Thru">
  <div class="midi-thru-section">
    <p class="section-help">
      MIDI Thru routes incoming messages from one port to the other — useful for
      chaining devices. Both ports are enabled by default.
    </p>

    <div class="field-group">
      <div class="checkbox-row">
        <input
          id="midi-thru-usb"
          type="checkbox"
          checked={thruUsb}
          onchange={handleThruUsbChange}
        />
        <label for="midi-thru-usb">USB → 5-pin DIN</label>
      </div>
      <p class="help-text">
        {#if thruUsb}
          <strong>Enabled:</strong> Messages received on USB MIDI are forwarded to the 5-pin DIN output.
        {:else}
          <strong>Disabled:</strong> USB MIDI input is not forwarded to the 5-pin DIN output.
        {/if}
      </p>
    </div>

    <div class="field-group">
      <div class="checkbox-row">
        <input
          id="midi-thru-din"
          type="checkbox"
          checked={thruDin}
          onchange={handleThruDinChange}
        />
        <label for="midi-thru-din">5-pin DIN → USB</label>
      </div>
      <p class="help-text">
        {#if thruDin}
          <strong>Enabled:</strong> Messages received on the 5-pin DIN input are forwarded to the USB MIDI output.
        {:else}
          <strong>Disabled:</strong> 5-pin DIN input is not forwarded to the USB MIDI output.
        {/if}
      </p>
    </div>
  </div>
</Accordion>

<style>
  .midi-thru-section {
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
  }

  .section-help {
    font-size: 0.875rem;
    color: var(--text-secondary, #666);
    margin: 0 0 0.25rem 0;
  }

  .field-group {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .checkbox-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .checkbox-row input[type="checkbox"] {
    width: 16px;
    height: 16px;
    cursor: pointer;
  }

  .checkbox-row label {
    cursor: pointer;
    font-weight: 500;
  }

  .help-text {
    font-size: 0.875rem;
    color: var(--text-secondary, #666);
    margin: 0;
  }
</style>
