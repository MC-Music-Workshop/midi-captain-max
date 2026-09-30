<script lang="ts">
  import type { DeviceType } from '$lib/types';

  interface Props {
    title: string;
    message?: string;
    confirmLabel: string;
    initial?: DeviceType;
    onPick: (device: DeviceType | null) => void; // null = cancelled
  }

  let { title, message: body, confirmLabel, initial = 'std10', onPick }: Props = $props();

  // Snapshot of the initial prop is intended: the picker owns the choice from here.
  // svelte-ignore state_referenced_locally
  let choice = $state<DeviceType>(initial);

  function onKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      e.preventDefault();
      onPick(null);
    }
  }
</script>

<svelte:window onkeydown={onKeydown} />

<div class="backdrop" role="presentation" tabindex="-1" onclick={() => onPick(null)} onkeydown={onKeydown}>
  <div
    class="dialog"
    role="dialog"
    aria-modal="true"
    aria-labelledby="device-type-picker-title"
    tabindex="-1"
    onclick={(e) => e.stopPropagation()}
    onkeydown={(e) => e.stopPropagation()}
  >
    <h2 id="device-type-picker-title">{title}</h2>
    {#if body}<p>{body}</p>{/if}
    <label for="device-type-picker-select">Device model:</label>
    <select id="device-type-picker-select" bind:value={choice}>
      <option value="std10">STD10 (10 buttons)</option>
      <option value="mini6">Mini6 (6 buttons)</option>
      <option value="nano4">NANO4 (4 buttons)</option>
      <option value="duo2">DUO2 (2 buttons)</option>
      <option value="one1">ONE (1 button)</option>
    </select>
    <div class="buttons">
      <button class="secondary" onclick={() => onPick(null)}>Cancel</button>
      <button onclick={() => onPick(choice)}>{confirmLabel}</button>
    </div>
  </div>
</div>

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }
  .dialog {
    background: var(--bg-primary, #1e1e1e);
    color: var(--text-primary, #ddd);
    border: 1px solid var(--border-color, #444);
    border-radius: 8px;
    padding: 20px;
    width: 340px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  h2 { margin: 0; font-size: 16px; }
  p { margin: 0; font-size: 13px; color: var(--text-secondary, #888); }
  select {
    padding: 6px 8px;
    background: var(--bg-tertiary, #333);
    color: inherit;
    border: 1px solid var(--border-color, #444);
    border-radius: 4px;
  }
  .buttons { display: flex; justify-content: flex-end; gap: 8px; margin-top: 6px; }
  button {
    padding: 6px 14px;
    background: var(--accent, #0078d4);
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
  }
  button.secondary {
    background: transparent;
    color: var(--text-secondary, #888);
    border: 1px solid var(--border-color, #444);
  }
</style>
