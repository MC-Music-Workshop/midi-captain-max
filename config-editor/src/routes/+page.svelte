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
    onDeviceConnected, onDeviceDisconnected, restartDevice, ejectDevice
  } from '$lib/api';
  import type { DetectedDevice } from '$lib/types';
  import ConfigForm from '$lib/components/ConfigForm.svelte';
  import DeviceSection from '$lib/components/DeviceSection.svelte';
  import ButtonsSection from '$lib/components/ButtonsSection.svelte';
  import EncoderSection from '$lib/components/EncoderSection.svelte';
  import ExpressionSection from '$lib/components/ExpressionSection.svelte';
  import DisplaySection from '$lib/components/DisplaySection.svelte';
  import FirmwareInstaller from '$lib/components/FirmwareInstaller.svelte';
  import { loadConfig, validate, normalizeConfig, config } from '$lib/formStore';

  let appVersion = $state('');
  
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
    
    const isValid = validate();
    if (!isValid) {
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
      if ($selectedDevice.has_config) {
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
      }
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
  
  <div class="editor-container">
    {#if $selectedDevice && !$isLoading}
      <ConfigForm onSave={saveToDevice}>
        <DeviceSection />
        <ButtonsSection />
        <EncoderSection />
        <ExpressionSection />
        <DisplaySection />
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
        <p>Connect a MIDI Captain device and select it above</p>
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
