<script lang="ts">
  import Accordion from './Accordion.svelte';
  import { config, setDevice, updateField } from '$lib/formStore';
  import type { DeviceType } from '$lib/types';
  
  function handleDeviceChange(e: Event) {
    const target = e.target as HTMLSelectElement;
    setDevice(target.value as DeviceType);
  }
  
  function handleGlobalChannelChange(e: Event) {
    const target = e.target as HTMLInputElement;
    const value = parseInt(target.value);
    // Clamp to valid MIDI channel range (1-16), store as 0-15
    const clamped = Math.max(1, Math.min(16, value));
    updateField('global_channel', clamped - 1);
  }

  function handleUsbDriveNameChange(e: Event) {
    const target = e.target as HTMLInputElement;
    updateField('usb_drive_name', target.value || undefined);
  }

  function handleDevModeChange(e: Event) {
    const target = e.target as HTMLInputElement;
    updateField('dev_mode', target.checked);
  }
  
  // Display channel as 1-16 (stored internally as 0-15)
  let globalChannel = $derived(($config.global_channel ?? 0) + 1);
  let devMode = $derived($config.dev_mode ?? false);
  let usbDriveName = $derived($config.usb_drive_name ?? '');

</script>

<Accordion title="Device Settings">
  <div class="device-section">
    <div class="field-group">
      <label for="device-type">Device Type:</label>
      <select 
        id="device-type"
        class="select"
        value={$config.device}
        onchange={handleDeviceChange}
      >
        <option value="std10">STD10 (10 buttons)</option>
        <option value="mini6">Mini6 (6 buttons)</option>
        <option value="nano4">NANO4 (4 buttons)</option>
        <option value="duo2">DUO2 (2 buttons)</option>
        <option value="one1">ONE (1 button)</option>
      </select>

      <p class="help-text">
        {#if $config.device === 'one1'}
          ONE supports 1 button only. No encoder, expression pedals, or display.
        {:else if $config.device === 'duo2'}
          DUO2 supports 2 buttons only. No encoder, expression pedals, or display.
        {:else if $config.device === 'nano4'}
          NANO4 supports 4 buttons only. Encoder and expression pedals are not available.
        {:else if $config.device === 'mini6'}
          Mini6 supports 6 buttons only. Encoder and expression pedals are not available.
        {:else}
          STD10 supports 10 buttons, encoder, and expression pedals.
        {/if}
      </p>
    </div>
    
    <div class="field-group">
      <label for="global-channel">Global MIDI Channel:</label>
      <div class="channel-input-group">
        <input 
          id="global-channel"
          type="number"
          class="input-number"
          value={globalChannel}
          onblur={handleGlobalChannelChange}
          min="1"
          max="16"
        />
      </div>
      <p class="help-text">
        Default MIDI channel for all buttons (1-16).
        Individual buttons can override this setting.
      </p>
    </div>

    <!-- USB Drive Name: hidden until CircuitPython 8.x upgrade ships.
         The backend plumbing (config field, boot.py label= support) is intact.
         On CP 7.x, storage.remount() doesn't accept label=, so this has no effect.
         Re-enable this block once the CP upgrade is deployed to users.
    <div class="field-group">
      <label for="usb-drive-name">USB Drive Name:</label>
      <input
        id="usb-drive-name"
        type="text"
        class="input-text"
        value={usbDriveName}
        onblur={handleUsbDriveNameChange}
        maxlength="11"
        placeholder="MIDICAPTAIN"
      />
      <p class="help-text">
        Name shown when the drive mounts on your computer (max 11 chars,
        letters/numbers/underscores). Leave blank to use "MIDICAPTAIN".
      </p>
    </div>
    -->

    <div class="field-group">
      <div class="checkbox-row">
        <input
          id="dev-mode"
          type="checkbox"
          checked={devMode}
          onchange={handleDevModeChange}
        />
        <label for="dev-mode">Development Mode</label>
      </div>
      <p class="help-text">
        {#if devMode}
          <strong>Development mode:</strong> USB drive always mounts on boot.
          Convenient for iterating on firmware, but not recommended for live use.
        {:else}
          <strong>Performance mode (default):</strong> USB drive is hidden on boot.
          Hold Switch 1 while powering on to temporarily enable it for file updates.
        {/if}
      </p>
    </div>
  </div>
</Accordion>

<style>
  .device-section {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }
  
  .field-group {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  
  label {
    font-weight: 500;
  }
  
  .select {
    padding: 0.5rem;
    border: 1px solid var(--border-color, #ccc);
    border-radius: 4px;
    font-size: 0.875rem;
    background: var(--bg-primary, white);
    color: var(--text-primary, inherit);
    max-width: 250px;
  }
  
  .input-number {
    width: 80px;
    padding: 0.5rem;
    border: 1px solid var(--border-color, #ccc);
    border-radius: 4px;
    font-size: 0.875rem;
  }

  .channel-input-group {
    display: flex;
    align-items: center;
    gap: 0.75rem;
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
