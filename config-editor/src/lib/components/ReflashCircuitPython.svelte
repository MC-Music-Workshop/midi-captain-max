<script lang="ts">
  import { onDestroy } from 'svelte';
  import { reflashCircuitpython, rpiRp2MountPath, scanDevices } from '$lib/api';
  import type { ReflashProgress } from '$lib/types';

  interface Props {
    /** When true, render an attention-grabbing CTA banner above the button.
     *  Set by FirmwareInstaller when an install was just refused due to a
     *  CP-version mismatch (issue #132 preflight). */
    highlight?: boolean;
    /** Called after a successful reflash so the parent can refresh device
     *  state (re-scan, re-read VERSION.txt etc.). */
    onComplete?: () => void;
  }

  let { highlight = false, onComplete }: Props = $props();

  type State =
    | { kind: 'idle' }
    | { kind: 'awaitingBootloader' }
    | { kind: 'copying'; message: string }
    | { kind: 'awaitingReboot'; message: string }
    | { kind: 'done' }
    | { kind: 'error'; message: string };

  let flow = $state<State>({ kind: 'idle' });
  let bootloaderPath = $state<string | null>(null);

  // Narrow `flow` into the message field where the branch carries one.
  // Centralised so template branches can just render `{statusMessage}`
  // without re-narrowing the union inline.
  let statusMessage = $derived(
    flow.kind === 'copying' || flow.kind === 'awaitingReboot' || flow.kind === 'error'
      ? flow.message
      : '',
  );

  // Poll handles — cleared on state change or cancel.
  let bootloaderPollTimer: ReturnType<typeof setInterval> | null = null;
  let rebootPollTimer: ReturnType<typeof setInterval> | null = null;

  function clearPollers() {
    if (bootloaderPollTimer !== null) {
      clearInterval(bootloaderPollTimer);
      bootloaderPollTimer = null;
    }
    if (rebootPollTimer !== null) {
      clearInterval(rebootPollTimer);
      rebootPollTimer = null;
    }
  }

  onDestroy(clearPollers);

  async function pollForBootloader() {
    try {
      const p = await rpiRp2MountPath();
      if (p !== null && flow.kind === 'awaitingBootloader') {
        bootloaderPath = p;
        clearPollers();
        await runReflash();
      }
    } catch {
      // Transient — keep polling.
    }
  }

  async function pollForCircuitpyReturn() {
    try {
      const devices = await scanDevices();
      if (devices.length > 0 && flow.kind === 'awaitingReboot') {
        clearPollers();
        flow = { kind: 'done' };
        onComplete?.();
      }
    } catch {
      // Transient.
    }
  }

  async function runReflash() {
    flow = {
      kind: 'copying',
      message: 'Copying CircuitPython 7.3.1 onto the bootloader…',
    };
    try {
      await reflashCircuitpython((p: ReflashProgress) => {
        // Echo Rust-side progress into our state machine. The Rust command's
        // last phase is 'done', but that just means bytes are written — we
        // still need to wait for the device to reboot back to CIRCUITPY, so
        // we map 'done' → our `awaitingReboot` state.
        switch (p.phase) {
          case 'copying':
            flow = { kind: 'copying', message: p.message };
            break;
          case 'awaitingReboot':
          case 'done':
            flow = { kind: 'awaitingReboot', message: p.message };
            break;
        }
      });
      // After the command resolves, start polling for CIRCUITPY to come back.
      flow = {
        kind: 'awaitingReboot',
        message:
          'CircuitPython 7.3.1 written. Waiting for the device to reboot back to CIRCUITPY…',
      };
      rebootPollTimer = setInterval(pollForCircuitpyReturn, 1500);
    } catch (e: any) {
      clearPollers();
      flow = {
        kind: 'error',
        message: e?.message ?? String(e),
      };
    }
  }

  async function startReflash() {
    // Fast-path: if RPI-RP2 is already mounted (user pre-staged the device into
    // bootloader mode), skip straight to the copy.
    try {
      const existing = await rpiRp2MountPath();
      if (existing !== null) {
        bootloaderPath = existing;
        await runReflash();
        return;
      }
    } catch {
      // Fall through to polling — the command may transiently fail on first
      // call while the OS settles.
    }
    flow = { kind: 'awaitingBootloader' };
    bootloaderPollTimer = setInterval(pollForBootloader, 1000);
  }

  function cancel() {
    clearPollers();
    flow = { kind: 'idle' };
    bootloaderPath = null;
  }

  function dismiss() {
    flow = { kind: 'idle' };
    bootloaderPath = null;
  }
</script>

{#if highlight && flow.kind === 'idle'}
  <div class="cta-banner">
    <strong>Need CircuitPython 7.3.1?</strong>
    Use the button below to reflash directly — no manual .uf2 download needed.
  </div>
{/if}

<button class="reflash-trigger" onclick={startReflash} disabled={flow.kind !== 'idle'}>
  Reflash CircuitPython 7.3.1
</button>

{#if flow.kind !== 'idle'}
  <div
    class="modal-overlay"
    role="dialog"
    aria-modal="true"
    aria-labelledby="reflash-title"
  >
    <div class="modal">
      <h3 id="reflash-title">Reflash CircuitPython 7.3.1</h3>

      {#if flow.kind === 'awaitingBootloader'}
        <p>To enter the RP2040 bootloader:</p>
        <ol>
          <li>Unplug the device from USB.</li>
          <li>Hold down <strong>Switch 1</strong> (top-left footswitch) / <strong>KEY0</strong>.</li>
          <li>Plug USB back in while still holding the switch.</li>
          <li>Release the switch once a drive named <code>RPI-RP2</code> appears.</li>
        </ol>
        <div class="status">
          <span class="spinner" aria-hidden="true"></span>
          Waiting for <code>RPI-RP2</code> to mount…
        </div>
        <div class="actions">
          <button class="secondary" onclick={cancel}>Cancel</button>
        </div>
      {:else if flow.kind === 'copying'}
        <div class="status">
          <span class="spinner" aria-hidden="true"></span>
          {statusMessage}
        </div>
        <p class="hint">
          Don't unplug the device — the bootloader needs the .uf2 to finish
          writing before it can reboot.
        </p>
      {:else if flow.kind === 'awaitingReboot'}
        <div class="status">
          <span class="spinner" aria-hidden="true"></span>
          {statusMessage}
        </div>
        <p class="hint">
          The RP2040 bootloader is handling the flash + reboot on its own.
          We're waiting for <code>CIRCUITPY</code> to remount.
        </p>
        <div class="actions">
          <button class="secondary" onclick={cancel}>
            Stop waiting (reflash continues on device)
          </button>
        </div>
      {:else if flow.kind === 'done'}
        <div class="status success">
          ✓ CircuitPython 7.3.1 installed.
        </div>
        <p>
          The device has rebooted back to <code>CIRCUITPY</code>. Now click
          <strong>Install Firmware</strong> to deploy MIDI Captain MAX onto the
          fresh CircuitPython.
        </p>
        <div class="actions">
          <button onclick={dismiss}>Close</button>
        </div>
      {:else if flow.kind === 'error'}
        <div class="status error">
          ✗ {statusMessage}
        </div>
        <div class="actions">
          <button class="secondary" onclick={cancel}>Close</button>
          <button onclick={startReflash}>Try again</button>
        </div>
      {/if}
    </div>
  </div>
{/if}

<style>
  .cta-banner {
    padding: 10px 12px;
    background: rgba(240, 173, 78, 0.15);
    border: 1px solid var(--warning);
    border-radius: 4px;
    color: var(--text-primary);
    font-size: 13px;
    line-height: 1.45;
  }
  .cta-banner strong {
    display: block;
    margin-bottom: 4px;
  }

  .reflash-trigger {
    align-self: flex-start;
    padding: 6px 12px;
    font-size: 13px;
    background: var(--bg-tertiary, var(--bg-secondary));
    color: var(--text-primary);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    cursor: pointer;
  }
  .reflash-trigger:hover:not(:disabled) {
    background: var(--bg-secondary);
    border-color: var(--accent);
  }
  .reflash-trigger:disabled {
    background: var(--disabled-bg);
    cursor: not-allowed;
    opacity: 0.6;
  }

  .modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.55);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    padding: 24px;
  }

  .modal {
    background: var(--bg-primary, #1e1e1e);
    color: var(--text-primary);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    padding: 20px 24px;
    max-width: 520px;
    width: 100%;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
    font-size: 14px;
    line-height: 1.5;
  }

  .modal h3 {
    margin: 0 0 12px 0;
    font-size: 16px;
  }

  .modal ol {
    margin: 8px 0;
    padding-left: 22px;
  }

  .modal li {
    margin: 4px 0;
  }

  .modal code {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    background: var(--bg-secondary);
    padding: 1px 5px;
    border-radius: 3px;
    font-size: 12px;
  }

  .status {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 12px;
    background: var(--bg-secondary);
    border-radius: 4px;
    margin-top: 8px;
  }

  .status.success {
    background: rgba(74, 124, 78, 0.15);
    border: 1px solid var(--success);
  }

  .status.error {
    background: var(--error-bg, rgba(229, 53, 53, 0.15));
    border: 1px solid var(--error-border, var(--error, #e53535));
    color: var(--error-text, var(--text-primary));
  }

  .hint {
    margin: 12px 0 0;
    color: var(--text-secondary);
    font-size: 13px;
  }

  .actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 16px;
  }

  .actions button {
    padding: 6px 14px;
    font-size: 13px;
    background: var(--accent);
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
  }

  .actions button.secondary {
    background: transparent;
    color: var(--text-primary);
    border: 1px solid var(--border-color);
  }

  .actions button:hover {
    opacity: 0.9;
  }

  .spinner {
    width: 14px;
    height: 14px;
    border: 2px solid var(--text-secondary);
    border-top-color: transparent;
    border-radius: 50%;
    display: inline-block;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }
</style>
