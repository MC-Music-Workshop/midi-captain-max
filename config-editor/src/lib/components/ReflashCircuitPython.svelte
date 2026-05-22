<script lang="ts">
  import { onDestroy } from 'svelte';
  import { enterBootloader, reflashCircuitpython, rpiRp2MountPath, scanDevices } from '$lib/api';
  import type { DetectedDevice, ReflashProgress } from '$lib/types';

  interface Props {
    /** When true, render an attention-grabbing CTA banner above the button.
     *  Reserved for callers that want to draw the eye to the reflash flow. */
    highlight?: boolean;
    /** Called after a successful reflash so the parent can refresh device
     *  state (re-scan, re-read VERSION.txt etc.). */
    onComplete?: () => void;
    /** Mounted CIRCUITPY/MIDICAPTAIN device. When provided, the modal first
     *  tries to drive the device into RP2040 ROM bootloader mode via the
     *  serial REPL (`enterBootloader`) so the user doesn't have to do it
     *  themselves. Without this prop the flow assumes RPI-RP2 is already
     *  mounted (used by the top-level banner). */
    device?: DetectedDevice | null;
  }

  let { highlight = false, onComplete, device = null }: Props = $props();

  type State =
    | { kind: 'idle' }
    | { kind: 'enteringBootloader' }
    | { kind: 'awaitingBootloader' }
    | { kind: 'copying'; message: string }
    | { kind: 'awaitingReboot'; message: string }
    | { kind: 'done' }
    | { kind: 'error'; message: string; showManualFallback: boolean };

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
  // Watchdog for the copying phase: a healthy copy + bootloader handoff
  // finishes in under ~10s. If we're still in `copying` after 60s, surface a
  // diagnostic CTA rather than letting the user stare at the spinner forever.
  let copyWatchdogTimer: ReturnType<typeof setTimeout> | null = null;
  let copyStalled = $state(false);
  // Same idea for `awaitingBootloader`: healthy auto-entry resolves in ~3s,
  // manual entry in however long the user takes to do the switch-hold dance.
  // 60s with no RPI-RP2 mount is long enough that something's wrong (device
  // powered off mid-entry, broken serial, mistaken click) — surface a banner
  // with manual recovery instructions instead of spinning indefinitely.
  let bootloaderWatchdogTimer: ReturnType<typeof setTimeout> | null = null;
  let bootloaderStalled = $state(false);

  function clearPollers() {
    if (bootloaderPollTimer !== null) {
      clearInterval(bootloaderPollTimer);
      bootloaderPollTimer = null;
    }
    if (rebootPollTimer !== null) {
      clearInterval(rebootPollTimer);
      rebootPollTimer = null;
    }
    if (copyWatchdogTimer !== null) {
      clearTimeout(copyWatchdogTimer);
      copyWatchdogTimer = null;
    }
    if (bootloaderWatchdogTimer !== null) {
      clearTimeout(bootloaderWatchdogTimer);
      bootloaderWatchdogTimer = null;
    }
    copyStalled = false;
    bootloaderStalled = false;
  }

  function startBootloaderWatchdog() {
    bootloaderStalled = false;
    bootloaderWatchdogTimer = setTimeout(() => {
      if (flow.kind === 'awaitingBootloader') {
        bootloaderStalled = true;
      }
    }, 20_000);
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
    copyStalled = false;
    copyWatchdogTimer = setTimeout(() => {
      // Only flip the stalled flag if we're still in copying — if the state
      // already advanced (or the user cancelled) we don't want to nag them.
      if (flow.kind === 'copying') {
        copyStalled = true;
      }
    }, 60_000);
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
        // Copy-phase errors aren't a serial-entry problem, so manual entry
        // instructions wouldn't help — leave the fallback off.
        showManualFallback: false,
      };
    }
  }

  async function startReflash() {
    // 1. Fast-path: if RPI-RP2 is already mounted (banner case, or user
    //    manually entered bootloader), skip everything and copy directly.
    try {
      const existing = await rpiRp2MountPath();
      if (existing !== null) {
        bootloaderPath = existing;
        await runReflash();
        return;
      }
    } catch {
      // Transient — fall through to the next step.
    }

    // 2. Device-driven entry: ask CP to reboot into the bootloader for us.
    if (device) {
      flow = { kind: 'enteringBootloader' };
      try {
        await enterBootloader(device.path);
      } catch (e: any) {
        // Serial reach failed — device may be too bricked to honor REPL
        // commands. Show the manual fallback so the user has a path forward.
        flow = {
          kind: 'error',
          message: e?.message ?? String(e),
          showManualFallback: true,
        };
        return;
      }
      flow = { kind: 'awaitingBootloader' };
      bootloaderPollTimer = setInterval(pollForBootloader, 1000);
      startBootloaderWatchdog();
      return;
    }

    // 3. No device prop: just wait for the user to enter bootloader manually.
    //    Rare — only happens if the banner case loses the RPI-RP2 mount
    //    between detection and modal open.
    flow = { kind: 'awaitingBootloader' };
    bootloaderPollTimer = setInterval(pollForBootloader, 1000);
    startBootloaderWatchdog();
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

      {#if flow.kind === 'enteringBootloader'}
        <div class="status">
          <span class="spinner" aria-hidden="true"></span>
          Telling the device to reboot into the RP2040 bootloader…
        </div>
        <p class="hint">
          Sending <code>microcontroller.on_next_reset(RunMode.UF2)</code> over
          the device's serial REPL. The <code>CIRCUITPY</code> drive will
          disappear and <code>RPI-RP2</code> should mount within ~3 s.
        </p>
      {:else if flow.kind === 'awaitingBootloader'}
        <p>Waiting for the device to reboot into <code>RPI-RP2</code> bootloader mode.</p>
        <p class="hint">
          Healthy auto-entry resolves in ~3 s. If nothing happens, see the
          <a
            href="https://github.com/MC-Music-Workshop/midi-captain-max/blob/main/docs/recovery-bootloader-entry.md"
            target="_blank"
            rel="noopener noreferrer"
          >manual recovery guide</a>.
        </p>
        <div class="status">
          <span class="spinner" aria-hidden="true"></span>
          Polling for <code>RPI-RP2</code>…
        </div>
        {#if bootloaderStalled}
          <div class="status error">
            No <code>RPI-RP2</code> mount detected within the timeout. The
            device may be powered off, the serial reach may have failed, or
            the click may have happened mid-power-cycle. Cancel, confirm the
            device is on and connected, and click
            <strong>Reflash CircuitPython 7.3.1</strong> again.
          </div>
        {/if}
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
        {#if copyStalled}
          <div class="status error">
            Copy hasn't completed in 60 seconds. The bootloader may not be
            accepting the write — try cancelling, unplugging, then re-entering
            <code>RPI-RP2</code> bootloader mode before retrying.
          </div>
        {/if}
        <div class="actions">
          <button class="secondary" onclick={cancel}>Cancel</button>
        </div>
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
        {#if flow.showManualFallback}
          <div class="manual-fallback">
            <p>
              <strong>Couldn't reach the device over serial.</strong> The most
              reliable next step is to drive the bootloader from a serial
              terminal by hand — usually works even when the GUI's attempt
              didn't.
            </p>
            <p>
              Full instructions (serial REPL first, physical BOOTSEL as a
              last resort):
              <br />
              <a
                href="https://github.com/MC-Music-Workshop/midi-captain-max/blob/main/docs/recovery-bootloader-entry.md"
                target="_blank"
                rel="noopener noreferrer"
              >
                docs/recovery-bootloader-entry.md
              </a>
            </p>
            <p class="hint">
              Once <code>RPI-RP2</code> mounts, the top-level reflash banner
              picks it up automatically and the rest of the flow takes over.
            </p>
          </div>
        {/if}
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

  .manual-fallback {
    margin-top: 12px;
    padding: 12px 14px;
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    font-size: 13px;
    line-height: 1.5;
  }
  .manual-fallback p {
    margin: 0 0 8px;
  }
  .manual-fallback a {
    color: var(--accent);
    text-decoration: underline;
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
