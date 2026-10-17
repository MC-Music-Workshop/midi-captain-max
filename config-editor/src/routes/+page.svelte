<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { get } from 'svelte/store';
  import { message, ask, open, save } from '@tauri-apps/plugin-dialog';
  import { getVersion } from '@tauri-apps/api/app';
  import {
    devices, selectedDevice, currentConfigRaw, workingOn,
    validationErrors, statusMessage, isLoading
  } from '$lib/stores';
  import {
    scanDevices, startDeviceWatcher, readConfigRaw, writeConfigRaw,
    onDeviceConnected, onDeviceDisconnected, restartDevice, ejectDevice,
    rpiRp2MountPath, detectOemV5Port, configsDir, openConfigFile, saveConfigFile,
    defaultConfig, deviceConfigType
  } from '$lib/api';
  import type { DetectedDevice, DeviceType } from '$lib/types';
  import {
    buttonStates, afterSaveToDevice, afterSaveToFileAs, fileName, workingOnLabel,
    type WorkingOn
  } from '$lib/workingOn';
  import DeviceTypePicker from '$lib/components/DeviceTypePicker.svelte';
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
  import { loadConfig, validate, normalizeConfig, markSaved, isDirty, config, currentPage } from '$lib/formStore';
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
  
  const DEVICE_LABELS: Record<DeviceType, string> = {
    std10: 'STD10', mini6: 'Mini6', nano4: 'NANO4', duo2: 'DUO2', one1: 'ONE',
  };

  // Promise-based device model picker (New Config…, and Save to Device when the
  // device's model can't be read). Resolves null when cancelled.
  let picker = $state<{
    title: string; message?: string; confirmLabel: string; initial?: DeviceType;
    resolve: (d: DeviceType | null) => void;
  } | null>(null);

  function pickDeviceType(opts: { title: string; message?: string; confirmLabel: string; initial?: DeviceType }) {
    return new Promise<DeviceType | null>(resolve => {
      picker = { ...opts, resolve };
    });
  }

  function resolvePicker(d: DeviceType | null) {
    picker?.resolve(d);
    picker = null;
  }

  // Everything that replaces what you're working on goes through here first.
  async function confirmDiscard(): Promise<boolean> {
    if (!$isDirty) return true;
    return ask('You have unsaved edits. Discard them?', {
      title: 'Unsaved Changes', kind: 'warning', okLabel: 'Discard', cancelLabel: 'Cancel'
    });
  }

  const errText = (e: any) => e?.message ?? String(e);

  let deviceConnected = $derived(
    $selectedDevice !== null && $devices.some(d => d.path === $selectedDevice!.path)
  );
  let states = $derived($workingOn ? buttonStates($workingOn, deviceConnected) : null);
  let workingOnDevice = $derived(
    $workingOn?.kind === 'device' && $selectedDevice !== null && $workingOn.device.path === $selectedDevice.path
  );

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
        if (exists) return;
        $devices = [...$devices, device];
        $statusMessage = `Device connected: ${device.name}`;

        const wasSelected = $selectedDevice?.name === device.name;
        const reconnectedWorkingOn = $workingOn?.kind === 'device' && $workingOn.device.name === device.name;

        if (reconnectedWorkingOn) {
          // Same device is back: re-enable Save to Device without touching edits.
          $selectedDevice = device;
          $workingOn = { kind: 'device', device };
          if (!$isDirty) {
            await new Promise(resolve => setTimeout(resolve, 500));
            await loadFromDevice(device);
          } else {
            $statusMessage = `${device.name} reconnected. Your unsaved edits are kept.`;
          }
        } else if ($workingOn === null) {
          // Nothing open: auto-select and load, as before.
          if ($devices.length === 1 || wasSelected) {
            // Small delay to ensure device is fully mounted before loading config
            await new Promise(resolve => setTimeout(resolve, 500));
            $selectedDevice = device;
            await loadFromDevice(device);
          }
        } else if ($selectedDevice === null) {
          // Something is open: give Save to Device a target, but never load over it.
          $selectedDevice = device;
        }
      });
      
      unlistenDisconnect = await onDeviceDisconnected(async (name) => {
        // Remove device by name. The form and any edits stay (D7); Save to
        // Device disables itself via `deviceConnected`. selectedDevice is kept
        // so the device is re-selected when it reconnects.
        $devices = $devices.filter(d => d.name !== name);
        $statusMessage = `Device disconnected: ${name}`;
      });
      
      // Auto-select if only one device
      if ($devices.length === 1) {
        await selectDevice($devices[0]);
      }

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
    if (rpiRp2PollTimer !== null) {
      clearInterval(rpiRp2PollTimer);
      rpiRp2PollTimer = null;
    }
  });

  function applyLoaded(configRaw: string, working: WorkingOn, status: string) {
    loadConfig(JSON.parse(configRaw));
    $currentConfigRaw = configRaw;
    $workingOn = working;
    $validationErrors = [];
    $statusMessage = status;
  }

  // Read the device's config into the form and start working on that device.
  // No discard prompt here — callers decide (see confirmDiscard).
  async function loadFromDevice(device: DetectedDevice, status = 'Config loaded from device') {
    $isLoading = true;
    try {
      // Don't gate on the snapshot's has_config — it's frozen at detection
      // time and can be stale (e.g. device re-detected mid-mount after the
      // post-install reboot). A genuinely missing config.json surfaces as an
      // error in the footer instead.
      const configRaw = await readConfigRaw(device.config_path);
      applyLoaded(configRaw, { kind: 'device', device }, status);
    } catch (e: any) {
      console.error('Error loading config:', e);
      $statusMessage = `Error reading config: ${errText(e)}`;
    } finally {
      $isLoading = false;
    }
  }

  // Picking a device loads it, even while working on a file (D12).
  async function selectDevice(device: DetectedDevice) {
    if ($workingOn && !(await confirmDiscard())) return;

    $selectedDevice = device;
    if (device.has_config) {
      await loadFromDevice(device, 'Config loaded successfully');
    } else {
      if ($workingOn?.kind === 'device') $workingOn = null;
      $statusMessage = 'No config.json found on device';
    }
  }

  async function reloadFromDevice() {
    if (!$selectedDevice || !(await confirmDiscard())) return;
    await loadFromDevice($selectedDevice, 'Config reloaded from device');
  }

  async function loadFromFile(path?: string) {
    if (!path && !(await confirmDiscard())) return;
    try {
      if (!path) {
        const picked = await open({
          title: 'Load config from file',
          defaultPath: await configsDir(),
          multiple: false,
          filters: [{ name: 'MIDI Captain config', extensions: ['json'] }],
        });
        if (typeof picked !== 'string') return; // cancelled
        path = picked;
      }
      applyLoaded(await openConfigFile(path), { kind: 'file', path }, `Loaded ${fileName(path)}`);
    } catch (e: any) {
      await message(errText(e), { title: 'Could not load file', kind: 'error' });
    }
  }

  async function reloadFromFile() {
    if ($workingOn?.kind !== 'file' || !(await confirmDiscard())) return;
    await loadFromFile($workingOn.path);
  }

  async function newConfig() {
    if (!(await confirmDiscard())) return;
    const device = await pickDeviceType({
      title: 'New config',
      message: 'Start from the default config for:',
      confirmLabel: 'Create',
    });
    if (!device) return;
    try {
      applyLoaded(await defaultConfig(device), { kind: 'new' }, `New ${DEVICE_LABELS[device]} config`);
    } catch (e: any) {
      await message(errText(e), { title: 'Could not create config', kind: 'error' });
    }
  }

  // Steps every save runs: commit the focused field, validate everything, and
  // produce the JSON to write. Returns null (after telling the user) on failure.
  async function prepareSave(): Promise<string | null> {
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
      return null;
    }
    return JSON.stringify(normalizeConfig(get(config)), null, 2);
  }

  // D8/D10: confirm before writing a config to a device of a different model.
  async function confirmDeviceType(device: DetectedDevice, configType: DeviceType): Promise<boolean> {
    let deviceType: DeviceType | null = null;
    try {
      deviceType = await deviceConfigType(device.path);
    } catch {
      // Unreadable: treated as unknown below.
    }
    if (deviceType === null) {
      deviceType = await pickDeviceType({
        title: 'Which model is this device?',
        message: "Its current config.json doesn't say, so choose its model.",
        confirmLabel: 'Continue',
        initial: configType,
      });
      if (deviceType === null) return false;
    }
    if (deviceType === configType) return true;
    return ask(
      `This device is set up as a ${DEVICE_LABELS[deviceType]}. Save a ${DEVICE_LABELS[configType]} config to it?`,
      { title: 'Device Type Mismatch', kind: 'warning', okLabel: 'Save Anyway', cancelLabel: 'Cancel' }
    );
  }

  async function saveToDevice(restart = false) {
    const device = $selectedDevice;
    const working = $workingOn;
    if (!device || !working || !deviceConnected) return;

    const configJson = await prepareSave();
    if (configJson === null) return;
    if (!(await confirmDeviceType(device, get(config).device ?? 'std10'))) return;

    $isLoading = true;
    try {
      await writeConfigRaw(device.config_path, configJson);

      const outcome = afterSaveToDevice(working, device);
      $workingOn = outcome.working;
      if (outcome.clearsDirty) {
        $currentConfigRaw = configJson;
        markSaved();
      }

      // The toolbar's sticky Save mode decides this — no per-save prompt. Plain
      // save leaves the device running the old config until the user restarts it
      // (footer says so, and the Restart Device button is right there).
      if (restart) {
        $statusMessage = 'Config saved';
        await doRestartDevice();
      } else {
        $statusMessage = 'Config saved — restart device to apply';
      }
    } catch (e: any) {
      $statusMessage = `Error saving config: ${errText(e)}`;
      await message($statusMessage, { title: 'Error', kind: 'error' });
    } finally {
      $isLoading = false;
    }
  }

  // Overwrite the open file.
  async function saveToFile() {
    if ($workingOn?.kind !== 'file') return;
    const path = $workingOn.path;
    const json = await prepareSave();
    if (json === null) return;
    try {
      await saveConfigFile(path, json);
      markSaved();
      $statusMessage = `Saved ${fileName(path)}`;
    } catch (e: any) {
      $statusMessage = `Error saving file: ${errText(e)}`;
      await message($statusMessage, { title: 'Error', kind: 'error' });
    }
  }

  // Save a copy to a chosen file; a new config becomes that file (D3).
  async function saveToFileAs() {
    const working = $workingOn;
    if (!working) return;
    const json = await prepareSave();
    if (json === null) return;
    try {
      const dir = await configsDir();
      const path = await save({
        title: 'Save config to file',
        defaultPath: working.kind === 'file' ? working.path : `${dir}/${get(config).device ?? 'config'}.json`,
        filters: [{ name: 'MIDI Captain config', extensions: ['json'] }],
      });
      if (!path) return; // cancelled
      await saveConfigFile(path, json);
      const outcome = afterSaveToFileAs(working, path);
      $workingOn = outcome.working;
      if (outcome.clearsDirty) markSaved();
      $statusMessage = `Saved ${fileName(path)}`;
    } catch (e: any) {
      $statusMessage = `Error saving file: ${errText(e)}`;
      await message($statusMessage, { title: 'Error', kind: 'error' });
    }
  }

  // Firmware install finished (D13): reload only when that would replace nothing
  // the user is working on.
  async function onFirmwareInstalled() {
    const device = $selectedDevice;
    if (device && ($workingOn === null || workingOnDevice)) {
      await loadFromDevice(device, 'Firmware installed; config reloaded from device');
    } else {
      $statusMessage = 'Firmware install finished. Your open config was not changed.';
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

    const editingThisDevice = workingOnDevice && $isDirty;
    if (editingThisDevice) {
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
      if (workingOnDevice) {
        $workingOn = null;
        $currentConfigRaw = '';
      }
      $statusMessage = `${ejectedName} ejected safely`;

      // Pick another connected device: load it only if nothing else is open.
      if ($devices.length > 0) {
        if ($workingOn === null) await selectDevice($devices[0]);
        else $selectedDevice = $devices[0];
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
    {#if $workingOn}
      <div class="working-on" title="What you're working on">
        <span class="working-on-kind">{$workingOn.kind === 'device' ? 'Device' : $workingOn.kind === 'file' ? 'File' : ''}</span>
        <strong>{workingOnLabel($workingOn)}</strong>
        {#if $isDirty}<span class="dot" title="Unsaved edits" aria-label="Unsaved edits">●</span>{/if}
      </div>
    {/if}
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
    {#if $workingOn && states && !$isLoading}
      <ConfigForm
        {states}
        onSaveToDevice={saveToDevice}
        onSaveToFile={saveToFile}
        onSaveToFileAs={saveToFileAs}
        onLoadFromFile={() => loadFromFile()}
        onNewConfig={newConfig}
      >
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
        {#if $selectedDevice}
          <FirmwareInstaller
            device={$selectedDevice}
            hasUnsavedChanges={$isDirty && workingOnDevice}
            onInstalled={onFirmwareInstalled}
          />
        {/if}
      </ConfigForm>
    {:else if $isLoading}
      <div class="loading">Loading config...</div>
    {:else}
      <div class="no-device">
        <p>Nothing open</p>
        <div class="empty-actions">
          <button onclick={() => loadFromFile()}>Load from File…</button>
          <button onclick={newConfig}>New Config…</button>
        </div>
        <p>Or connect a MIDI Captain device and select it above.</p>
        {#if $selectedDevice}
          <FirmwareInstaller
            device={$selectedDevice}
            hasUnsavedChanges={false}
            onInstalled={onFirmwareInstalled}
          />
        {/if}
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
      {#if $isDirty}
        <span class="unsaved">● Unsaved changes</span>
      {/if}
      {#if states?.reloadFromFile.visible}
        <button class="secondary" onclick={reloadFromFile} disabled={$isLoading}>
          Reload from File
        </button>
      {/if}
      <button
        class="secondary"
        onclick={reloadFromDevice}
        disabled={!deviceConnected || $isLoading}
        title={deviceConnected ? '' : 'No device connected'}
      >
        Reload from Device
      </button>
      <button 
        class="secondary"
        onclick={doRestartDevice}
        disabled={!deviceConnected || $isLoading}
      >
        Restart Device
      </button>
      <button
        class="secondary"
        onclick={doEjectDevice}
        disabled={!deviceConnected || $isLoading}
      >
        Eject
      </button>
    </div>
  </footer>

  {#if picker}
    <DeviceTypePicker
      title={picker.title}
      message={picker.message}
      confirmLabel={picker.confirmLabel}
      initial={picker.initial}
      onPick={resolvePicker}
    />
  {/if}
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

  .empty-actions {
    display: flex;
    gap: 12px;
    margin: 12px 0;
  }

  .working-on {
    display: flex;
    align-items: baseline;
    gap: 6px;
    font-size: 14px;
  }

  .working-on-kind {
    color: var(--text-secondary);
    font-size: 12px;
  }

  .working-on .dot {
    color: #dcdcaa;
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
