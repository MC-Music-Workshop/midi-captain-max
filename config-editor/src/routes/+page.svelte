<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { get } from 'svelte/store';
  import { message, ask } from '@tauri-apps/plugin-dialog';
  import { getVersion } from '@tauri-apps/api/app';
  import {
    devices, selectedDevice, currentConfigRaw,
    hasUnsavedChanges, validationErrors, statusMessage, isLoading
  } from '$lib/stores';
  import {
    scanDevices, startDeviceWatcher, readConfigRaw, writeConfigRaw,
    onDeviceConnected, onDeviceDisconnected, restartDevice, ejectDevice,
    rpiRp2MountPath, detectOemV5Port
  } from '$lib/api';
  import type { DetectedDevice } from '$lib/types';
  import ConfigForm from '$lib/components/ConfigForm.svelte';
  import DeviceSection from '$lib/components/DeviceSection.svelte';
  import PageBar from '$lib/components/PageBar.svelte';
  import PageSettingsSection from '$lib/components/PageSettingsSection.svelte';
  import ButtonsSection from '$lib/components/ButtonsSection.svelte';
  import EncoderSection from '$lib/components/EncoderSection.svelte';
  import ExpressionSection from '$lib/components/ExpressionSection.svelte';
  import DisplaySection from '$lib/components/DisplaySection.svelte';
  import MidiThruSection from '$lib/components/MidiThruSection.svelte';
import PageControlSection from '$lib/components/PageControlSection.svelte';
  import FirmwareInstaller from '$lib/components/FirmwareInstaller.svelte';
  import ReflashCircuitPython from '$lib/components/ReflashCircuitPython.svelte';
  import { loadConfig, validate, normalizeConfig, config, currentPage } from '$lib/formStore';
  import { validateAllPages } from '$lib/validation';

  let appVersion = $state('');

  // RPI-RP2 (RP2040 ROM bootloader) detection state. Polled at app level so
  // the reflash affordance only surfaces when the user has actually staged
  // the device into bootloader mode — no clutter in the normal UI.
  let rpiRp2DetectedPath = $state<string | null>(null);
  // Possible OEM FW5+ device (CDC port present, no device volume mounted).
  // Heuristic — the banner requires explicit user action; never auto-touch.
  let oemV5Port = $state<string | null>(null);
  let rpiRp2PollTimer: ReturnType<typeof setInterval> | null = null;

  // Event listener cleanup functions
  let unlistenConnect: (() => void) | undefined;
  let unlistenDisconnect: (() => void) | undefined;
  let keydownHandler: ((e: KeyboardEvent) => void) | undefined;
  
  onMount(async () => {
    try {
      appVersion = await getVersion();

      // Initial device scan
      $devices = await scanDevices();
      console.log('Devices found:', $devices);
      
      // Start watching for device changes
      await startDeviceWatcher();
      
      // Listen for device events (store cleanup functions)
      unlistenConnect = await onDeviceConnected(async (device) => {
        // Deduplicate: check if device is already in the list
        const exists = $devices.some(d => d.path === device.path);
        if (!exists) {
          $devices = [...$devices, device];
          $statusMessage = `Device connected: ${device.name}`;
          
          // Auto-select if device was previously selected or if it's the only one
          const shouldAutoSelect = $devices.length === 1 || 
            ($selectedDevice && $selectedDevice.path === device.path);
          
          if (shouldAutoSelect) {
            // Small delay to ensure device is fully mounted before loading config
            await new Promise(resolve => setTimeout(resolve, 500));
            
            // Force reload config by reading directly from device
            $selectedDevice = device;
            $isLoading = true;
            
            try {
              const configRaw = await readConfigRaw(device.config_path);
              const configObj = JSON.parse(configRaw);
              
              // Load into form store
              loadConfig(configObj);
              
              $currentConfigRaw = configRaw;
              $hasUnsavedChanges = false;
              $validationErrors = [];
              $statusMessage = 'Config reloaded from device';
            } catch (e: any) {
              $currentConfigRaw = '';
              $statusMessage = `Error loading config: ${e.message || e}`;
            } finally {
              $isLoading = false;
            }
          }
        }
      });
      
      unlistenDisconnect = await onDeviceDisconnected(async (name) => {
        const wasSelected = $selectedDevice?.name === name;
        
        // Remove device by name
        $devices = $devices.filter(d => d.name !== name);
        
        if (wasSelected) {
          if ($hasUnsavedChanges) {
            await message(
              `Device "${name}" was disconnected. Your unsaved changes have been lost.`,
              { title: 'Device Disconnected', kind: 'warning' }
            );
          }
          // Don't clear selectedDevice - keep it so we can auto-select when it reconnects
          $currentConfigRaw = '';
          $hasUnsavedChanges = false;
        }
        
        $statusMessage = `Device disconnected: ${name}`;
      });
      
      // Auto-select if only one device
      if ($devices.length === 1) {
        await selectDevice($devices[0]);
      }
      
      // Add keyboard shortcut handler (⌘S to save). Cleanup runs in onDestroy.
      keydownHandler = async (e: KeyboardEvent) => {
        if (e.metaKey && e.key === 's') {
          e.preventDefault();
          if ($selectedDevice && $hasUnsavedChanges) {
            await saveToDevice();
          }
        }
      };
      document.addEventListener('keydown', keydownHandler);

      // Poll for RPI-RP2 bootloader presence at 2s. Cheap call (one filesystem
      // read_dir on /Volumes); UI affordance only renders when detected.
      const pollRpiRp2 = async () => {
        try {
          rpiRp2DetectedPath = await rpiRp2MountPath();
          // Only look for the OEM-v5 signature when there's nothing better
          // to show: no bootloader mounted and no device detected.
          oemV5Port =
            !rpiRp2DetectedPath && $devices.length === 0
              ? await detectOemV5Port()
              : null;
        } catch {
          // Transient — keep polling on next tick.
        }
      };
      await pollRpiRp2();
      rpiRp2PollTimer = setInterval(pollRpiRp2, 2000);
    } catch (e: any) {
      $statusMessage = `Error initializing: ${e.message || e}`;
    }
  });

  onDestroy(() => {
    // Clean up event listeners to prevent memory leaks
    unlistenConnect?.();
    unlistenDisconnect?.();
    if (keydownHandler) {
      document.removeEventListener('keydown', keydownHandler);
    }
    if (rpiRp2PollTimer !== null) {
      clearInterval(rpiRp2PollTimer);
      rpiRp2PollTimer = null;
    }
  });
  
  async function selectDevice(device: DetectedDevice) {
    console.log('selectDevice called with:', device);
    
    if ($hasUnsavedChanges) {
      if (!confirm('You have unsaved changes. Discard them?')) {
        return;
      }
    }
    
    $selectedDevice = device;
    $isLoading = true;
    
    try {
      if (device.has_config) {
        console.log('Reading config from:', device.config_path);
        const configRaw = await readConfigRaw(device.config_path);
        console.log('Config raw loaded, length:', configRaw.length);
        const configObj = JSON.parse(configRaw);
        console.log('Config parsed:', configObj);
        
        // Load into form store
        loadConfig(configObj);
        console.log('Config loaded into form store');
        
        $currentConfigRaw = configRaw;
        $hasUnsavedChanges = false;
        $validationErrors = [];
        $statusMessage = 'Config loaded successfully';
      } else {
        console.log('No config found on device');
        $currentConfigRaw = '';
        $statusMessage = 'No config.json found on device';
      }
    } catch (e: any) {
      console.error('Error loading config:', e);
      $statusMessage = `Error reading config: ${e.message || e}`;
    } finally {
      $isLoading = false;
    }
  }
  
  async function saveToDevice() {
    if (!$selectedDevice) return;

    // Field edits commit on blur, and WebKit doesn't blur the focused input
    // when Save is clicked (or on ⌘S) — force it so the save includes an
    // in-flight edit instead of silently dropping it.
    if (document.activeElement instanceof HTMLElement) document.activeElement.blur();

    const isValid = validate();
    // D5: all pages must pass, not just the rendered one. Non-active-page
    // failures land in the footer error list as prefixed summary lines.
    const pageErrors = validateAllPages(get(config));
    $validationErrors = pageErrors;
    if (!isValid || pageErrors.length > 0) {
      await message('Please fix validation errors before saving', {
        title: 'Validation Error',
        kind: 'error'
      });
      return;
    }

    $isLoading = true;
    
    try {
      const configObj = normalizeConfig(get(config));
      const configJson = JSON.stringify(configObj, null, 2);
      
      await writeConfigRaw($selectedDevice.config_path, configJson);
      
      $currentConfigRaw = configJson;
      $hasUnsavedChanges = false;
      $statusMessage = 'Config saved — restart device to apply';

      const shouldRestart = await ask(
        'Config saved! Restart device to apply changes?',
        { title: 'Config Saved', kind: 'info', okLabel: 'Restart', cancelLabel: 'Later' }
      );

      if (shouldRestart) {
        await doRestartDevice();
      }
    } catch (e: any) {
      $statusMessage = `Error saving config: ${e.message || e}`;
      await message($statusMessage, { title: 'Error', kind: 'error' });
    } finally {
      $isLoading = false;
    }
  }
  
  async function reloadFromDevice() {
    console.log('reloadFromDevice called, selectedDevice:', $selectedDevice);
    if (!$selectedDevice) return;
    
    $isLoading = true;
    try {
      // Don't gate on the snapshot's has_config — it's frozen at detection
      // time and can be stale (e.g. device re-detected mid-mount after the
      // post-install reboot), which turned this button into a silent no-op.
      // Attempt the read; a genuinely missing config.json surfaces as an
      // error in the footer instead.
      console.log('Reloading config from:', $selectedDevice.config_path);
      const configRaw = await readConfigRaw($selectedDevice.config_path);
      console.log('Config reloaded, length:', configRaw.length);
      const configObj = JSON.parse(configRaw);

      // Load into form store
      loadConfig(configObj);

      $currentConfigRaw = configRaw;
      $hasUnsavedChanges = false;
      $validationErrors = [];
      $statusMessage = 'Config reloaded from device';
    } catch (e: any) {
      console.error('Error reloading config:', e);
      $statusMessage = `Error reloading config: ${e.message || e}`;
    } finally {
      $isLoading = false;
    }
  }
  
  async function doRestartDevice() {
    if (!$selectedDevice) return;

    try {
      await restartDevice($selectedDevice.config_path);
      $statusMessage = 'Device restarting with new configuration...';
    } catch (e: any) {
      console.error('Restart failed:', e);
      await message(
        'Could not restart automatically. Please restart your MIDI Captain:\n\n' +
        '1. Turn off using the power button on the back\n' +
        '2. Wait a moment\n' +
        '3. Turn it back on\n\n' +
        'The device will start up with the new configuration.',
        { title: 'Manual Restart Needed', kind: 'warning' }
      );
      $statusMessage = 'Restart failed — please restart device manually';
    }
  }
  
  async function doEjectDevice() {
    if (!$selectedDevice) return;

    if ($hasUnsavedChanges) {
      const proceed = await ask(
        'You have unsaved changes that will be lost. Eject anyway?',
        { title: 'Unsaved Changes', kind: 'warning', okLabel: 'Eject', cancelLabel: 'Cancel' }
      );
      if (!proceed) return;
    }

    const ejectedName = $selectedDevice.name;

    try {
      await ejectDevice($selectedDevice.config_path);

      // Clear state for ejected device — the disconnect watcher will also
      // fire, but we update immediately to avoid stale UI.
      $devices = $devices.filter(d => d.config_path !== $selectedDevice!.config_path);
      $selectedDevice = null;
      $currentConfigRaw = '';
      $hasUnsavedChanges = false;
      $statusMessage = `${ejectedName} ejected safely`;

      // Auto-select another device if one is still connected
      if ($devices.length > 0) {
        await selectDevice($devices[0]);
      }
    } catch (e: any) {
      console.error('Eject failed:', e);
      await message(
        `Could not eject automatically: ${e.message || e}\n\n` +
        'Please eject the device from your file manager.',
        { title: 'Eject Failed', kind: 'warning' }
      );
    }
  }

</script>

<main>
  <header>
    <div class="title-group">
      <h1>MIDI Captain MAX Config Editor</h1>
      {#if appVersion}
        <span class="version">v{appVersion}</span>
      {/if}
    </div>
    <div class="device-selector">
      {#if $devices.length === 0}
        <span class="no-device">No device connected</span>
      {:else}
        <select 
          value={$selectedDevice?.name ?? ''} 
          onchange={(e) => {
            const device = $devices.find(d => d.name === e.currentTarget.value);
            if (device) selectDevice(device);
          }}
        >
          <option value="" disabled>Select device...</option>
          {#each $devices as device}
            <option value={device.name}>{device.name}</option>
          {/each}
        </select>
      {/if}
    </div>
  </header>

  {#if rpiRp2DetectedPath}
    <div class="rpi-banner" role="status">
      <span class="label">
        <strong>RPI-RP2 bootloader detected</strong> at
        <code>{rpiRp2DetectedPath}</code>. Reflash CircuitPython 7.3.1 directly
        from here — the device will reboot back to <code>CIRCUITPY</code>
        automatically.
      </span>
      <ReflashCircuitPython
        onComplete={async () => {
          // Once the device returns to CIRCUITPY, refresh the picker so the
          // user can immediately hit Install Firmware. The device watcher's
          // connect event should also cover this; the explicit scan handles
          // platforms where the watcher lags.
          $devices = await scanDevices();
          rpiRp2DetectedPath = null;
        }}
      />
    </div>
  {/if}

  {#if !rpiRp2DetectedPath && oemV5Port}
    <div class="rpi-banner oem-v5" role="status">
      <span class="label">
        <strong>Possible PaintAudio OEM FW5 device</strong> on
        <code>{oemV5Port}</code>. FW5 pedals can't be configured here, but
        they can be migrated to MIDI Captain MAX.
        <strong>Migration replaces the OEM firmware and erases its on-pedal
        configs</strong> — to back up first, power on holding Switch&nbsp;1
        and copy the pedal's drive to your computer. Only proceed if this
        port is your MIDI Captain, not another Pico-based device.
      </span>
      <ReflashCircuitPython
        oemV5Port={oemV5Port}
        triggerLabel="Migrate to MIDI Captain MAX"
        onComplete={async () => {
          $devices = await scanDevices();
          oemV5Port = null;
          // The reflash renames the volume (e.g. MIDICAPTAIN → CIRCUITPY),
          // so name-based reselection can't match — pick the device up
          // directly when it's unambiguous.
          if ($devices.length === 1) {
            await selectDevice($devices[0]);
          }
        }}
      />
    </div>
  {/if}


  <div class="editor-container">
    {#if $selectedDevice && !$isLoading}
      <ConfigForm onSave={saveToDevice}>
        <DeviceSection />
        <PageBar />
        <!-- Keyed by page identity: switching pages rebuilds these sections'
             DOM from the new page's data, so no input state (e.g. typed text
             not yet committed by blur) can leak between pages. -->
        {#key $currentPage?.__uiId}
          <PageSettingsSection />
          <ButtonsSection />
          <EncoderSection />
          <ExpressionSection />
        {/key}
        <DisplaySection />
        <MidiThruSection />
        <PageControlSection />
        <FirmwareInstaller
          device={$selectedDevice}
          hasUnsavedChanges={$hasUnsavedChanges}
          onInstalled={reloadFromDevice}
        />
      </ConfigForm>
    {:else if $isLoading}
      <div class="loading">Loading config...</div>
    {:else}
      <div class="no-device">
        <p>No device selected</p>
        <p>Connect a MIDI Captain device and select it above.</p>
      </div>
    {/if}
  </div>
  
  {#if $validationErrors.length > 0}
    <div class="errors">
      <strong>Validation Errors:</strong>
      <ul>
        {#each $validationErrors as error}
          <li>{error}</li>
        {/each}
      </ul>
    </div>
  {/if}
  
  <footer>
    <div class="status">{$statusMessage}</div>
    <div class="actions">
      {#if $hasUnsavedChanges}
        <span class="unsaved">● Unsaved changes</span>
      {/if}
      <button 
        class="secondary"
        onclick={reloadFromDevice} 
        disabled={!$selectedDevice || $isLoading}
      >
        Reload
      </button>
      <button 
        class="secondary"
        onclick={doRestartDevice}
        disabled={!$selectedDevice || $isLoading}
      >
        Restart Device
      </button>
      <button
        class="secondary"
        onclick={doEjectDevice}
        disabled={!$selectedDevice || $isLoading}
      >
        Eject
      </button>
    </div>
  </footer>
</main>

<style>
  :global(body) {
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    
    /* Light mode defaults */
    --bg-primary: #ffffff;
    --bg-secondary: #f5f5f5;
    --bg-tertiary: #e0e0e0;
    --text-primary: #1e1e1e;
    --text-secondary: #666666;
    --border-color: #d0d0d0;
    --accent: #0078d4;
    --accent-hover: #1084d8;
    --success: #4a7c4e;
    --warning: #f0ad4e;
    --error-bg: #fce4e4;
    --error-border: #f5c6cb;
    --error-text: #a94442;
    --disabled-bg: #cccccc;
    
    background: var(--bg-primary);
    color: var(--text-primary);
  }

  @media (prefers-color-scheme: dark) {
    :global(body) {
      --bg-primary: #1e1e1e;
      --bg-secondary: #2d2d2d;
      --bg-tertiary: #3c3c3c;
      --text-primary: #d4d4d4;
      --text-secondary: #888888;
      --border-color: #404040;
      --accent: #0078d4;
      --accent-hover: #1084d8;
      --success: #4a7c4e;
      --warning: #f0ad4e;
      --error-bg: #3c1f1f;
      --error-border: #5c2f2f;
      --error-text: #f48771;
      --disabled-bg: #555555;
    }
  }
  
  main {
    display: flex;
    flex-direction: column;
    height: 100vh;
  }
  
  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 20px;
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border-color);
  }

  .title-group {
    display: flex;
    align-items: baseline;
    gap: 8px;
  }

  h1 {
    margin: 0;
    font-size: 18px;
    font-weight: 500;
  }

  .version {
    font-size: 12px;
    color: var(--text-secondary);
  }
  
  .device-selector select {
    padding: 6px 12px;
    font-size: 14px;
    background: var(--bg-tertiary);
    color: var(--text-primary);
    border: 1px solid var(--border-color);
    border-radius: 4px;
  }
  
  .no-device {
    color: var(--text-secondary);
    font-style: italic;
  }

  .rpi-banner.oem-v5 {
    /* Red-shifted variant: heuristic detection + firmware-replacing action. */
    background: rgba(220, 82, 82, 0.12);
    border-color: var(--danger, #c0605c);
  }

  .rpi-banner {
    margin: 12px 20px 0;
    padding: 12px 16px;
    background: rgba(240, 173, 78, 0.15);
    border: 1px solid var(--warning);
    border-radius: 6px;
    color: var(--text-primary);
    font-size: 13px;
    line-height: 1.5;
    display: flex;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
  }

  .rpi-banner .label {
    flex: 1;
    min-width: 240px;
  }

  .rpi-banner code {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    background: var(--bg-tertiary, var(--bg-primary));
    padding: 1px 5px;
    border-radius: 3px;
    font-size: 12px;
  }
  
  .editor-container {
    flex: 1;
    padding: 20px;
    overflow: hidden;
  }
  
  .errors {
    padding: 12px 20px;
    background: var(--error-bg);
    border-top: 1px solid var(--error-border);
    color: var(--error-text);
  }
  
  .errors ul {
    margin: 8px 0 0 0;
    padding-left: 20px;
  }
  
  footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 20px;
    background: var(--bg-secondary);
    border-top: 1px solid var(--border-color);
  }
  
  .status {
    color: var(--text-secondary);
    font-size: 13px;
  }
  
  .actions {
    display: flex;
    align-items: center;
    gap: 16px;
  }
  
  .unsaved {
    color: #dcdcaa;
    font-size: 13px;
  }
  
  button {
    padding: 8px 16px;
    font-size: 14px;
    background: var(--accent);
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
  }
  
  button.secondary {
    background: transparent;
    color: var(--text-secondary);
    border: 1px solid var(--border-color);
  }
  
  button:hover:not(:disabled) {
    background: var(--accent-hover);
  }
  
  button.secondary:hover:not(:disabled) {
    background: var(--bg-tertiary);
    color: var(--text-primary);
  }
  
  button:disabled {
    background: var(--disabled-bg);
    cursor: not-allowed;
  }
  
  button.secondary:disabled {
    background: transparent;
    color: var(--text-secondary);
    opacity: 0.5;
  }
</style>
