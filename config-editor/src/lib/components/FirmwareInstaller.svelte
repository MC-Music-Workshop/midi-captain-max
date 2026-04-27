<script lang="ts">
  import { ask, message } from '@tauri-apps/plugin-dialog';
  import { getFirmwareVersions, installFirmware } from '$lib/api';
  import type {
    DetectedDevice,
    FirmwareVersions,
    InstallProgress,
    InstallReport,
  } from '$lib/types';

  interface Props {
    device: DetectedDevice | null;
    hasUnsavedChanges: boolean;
    onInstalled?: () => void;
  }

  let { device, hasUnsavedChanges, onInstalled }: Props = $props();

  let resetConfig = $state(false);
  let installing = $state(false);
  let progress = $state<InstallProgress | null>(null);
  let report = $state<InstallReport | null>(null);
  let errorMsg = $state('');
  let versions = $state<FirmwareVersions | null>(null);

  // Re-fetch versions whenever the selected device changes or after a fresh
  // install so the UI reflects what's actually on disk now.
  async function refreshVersions(d: DetectedDevice | null) {
    if (!d) {
      versions = null;
      return;
    }
    try {
      versions = await getFirmwareVersions(d.path);
    } catch {
      versions = null;
    }
  }

  $effect(() => {
    refreshVersions(device);
  });

  let isUpgrade = $derived(
    versions !== null && versions.device !== null && versions.device !== versions.bundled,
  );
  let isUpToDate = $derived(
    versions !== null && versions.device === versions.bundled,
  );

  let percent = $derived(
    progress && progress.total > 0
      ? Math.round((progress.current / progress.total) * 100)
      : 0,
  );

  async function startInstall() {
    if (!device) return;

    if (hasUnsavedChanges) {
      const proceed = await ask(
        'You have unsaved config changes. Install firmware anyway? Unsaved edits to config.json will be discarded.',
        { title: 'Unsaved Changes', kind: 'warning', okLabel: 'Install', cancelLabel: 'Cancel' },
      );
      if (!proceed) return;
    }

    if (resetConfig) {
      const proceed = await ask(
        'Reset config will overwrite the device\'s config.json with the bundled template. Your customizations will be lost. Continue?',
        { title: 'Reset Config', kind: 'warning', okLabel: 'Reset and Install', cancelLabel: 'Cancel' },
      );
      if (!proceed) return;
    }

    installing = true;
    progress = null;
    report = null;
    errorMsg = '';

    try {
      report = await installFirmware(device.path, resetConfig, (p) => {
        progress = p;
      });
      onInstalled?.();
      await refreshVersions(device);
    } catch (e: any) {
      errorMsg = e?.message ?? String(e);
      await message(`Firmware install failed:\n\n${errorMsg}`, { title: 'Install Failed', kind: 'error' });
    } finally {
      installing = false;
    }
  }

  function phaseLabel(phase: string): string {
    switch (phase) {
      case 'planning': return 'Preparing';
      case 'copy': return 'Copying';
      case 'skip': return 'Skipping';
      case 'delete': return 'Removing';
      case 'manifest': return 'Writing manifest';
      case 'done': return 'Done';
      default: return phase;
    }
  }
</script>

<section class="installer">
  <h3>Firmware Installation</h3>

  {#if versions}
    <div class="versions">
      <div class="version-row">
        <span class="version-label">Installed:</span>
        {#if versions.device === null}
          <span class="version-value oem">OEM (no VERSION file)</span>
        {:else}
          <span class="version-value">{versions.device}</span>
        {/if}
      </div>
      <div class="version-row">
        <span class="version-label">Available:</span>
        <span class="version-value">{versions.bundled}</span>
        {#if isUpToDate}
          <span class="badge up-to-date">up to date</span>
        {:else if isUpgrade}
          <span class="badge upgrade">upgrade</span>
        {:else if versions.device === null}
          <span class="badge first-install">first install</span>
        {/if}
      </div>
    </div>
  {/if}

  <label class="reset-toggle">
    <input type="checkbox" bind:checked={resetConfig} disabled={installing} />
    Reset config.json to bundled defaults
  </label>

  <button onclick={startInstall} disabled={!device || installing}>
    {installing ? 'Installing...' : 'Install Firmware'}
  </button>

  {#if installing && progress}
    <div class="progress">
      <progress value={percent} max="100"></progress>
      <div class="progress-label">
        <span class="phase">{phaseLabel(progress.phase)}</span>
        <span class="counts">{progress.current} / {progress.total}</span>
      </div>
      {#if progress.file}
        <div class="file" title={progress.file}>{progress.file}</div>
      {/if}
    </div>
  {/if}

  {#if report && !installing}
    <div class="result success">
      <strong>Installed firmware {report.version}</strong>
      <ul>
        <li>Copied: {report.files_copied}</li>
        <li>Skipped (unchanged): {report.files_skipped}</li>
        <li>Removed (stale): {report.files_deleted}</li>
        <li>Config: {report.config_preserved ? 'preserved' : 'reset'}</li>
      </ul>
    </div>
  {/if}

  {#if errorMsg}
    <div class="result error">
      <strong>Error:</strong> {errorMsg}
    </div>
  {/if}
</section>

<style>
  .installer {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 12px;
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 4px;
  }

  .versions {
    display: flex;
    flex-direction: column;
    gap: 2px;
    font-size: 13px;
    padding-bottom: 6px;
    border-bottom: 1px solid var(--border-color);
  }

  .version-row {
    display: flex;
    align-items: baseline;
    gap: 8px;
  }

  .version-label {
    color: var(--text-secondary);
    min-width: 80px;
  }

  .version-value {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    color: var(--text-primary);
  }

  .version-value.oem {
    font-style: italic;
    color: var(--text-secondary);
    font-family: inherit;
  }

  .badge {
    font-size: 11px;
    padding: 1px 6px;
    border-radius: 3px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .badge.up-to-date {
    background: rgba(74, 124, 78, 0.2);
    color: var(--success);
  }

  .badge.upgrade {
    background: rgba(240, 173, 78, 0.2);
    color: var(--warning);
  }

  .badge.first-install {
    background: rgba(0, 120, 212, 0.2);
    color: var(--accent);
  }

  h3 {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
  }

  .reset-toggle {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    color: var(--text-primary);
  }

  button {
    align-self: flex-start;
    padding: 8px 16px;
    font-size: 14px;
    background: var(--accent);
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
  }

  button:disabled {
    background: var(--disabled-bg);
    cursor: not-allowed;
  }

  button:hover:not(:disabled) {
    background: var(--accent-hover);
  }

  .progress {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  progress {
    width: 100%;
    height: 8px;
  }

  .progress-label {
    display: flex;
    justify-content: space-between;
    font-size: 12px;
    color: var(--text-secondary);
  }

  .phase {
    text-transform: capitalize;
  }

  .file {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 11px;
    color: var(--text-secondary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .result {
    padding: 10px 12px;
    border-radius: 4px;
    font-size: 13px;
  }

  .result.success {
    background: rgba(74, 124, 78, 0.15);
    border: 1px solid var(--success);
    color: var(--text-primary);
  }

  .result.error {
    background: var(--error-bg);
    border: 1px solid var(--error-border);
    color: var(--error-text);
  }

  .result ul {
    margin: 6px 0 0 0;
    padding-left: 20px;
  }
</style>
