<script lang="ts">
  import type { KeytimesMessage, MessageType } from '$lib/types';
  import { MESSAGE_TYPE_LABELS } from '$lib/types';
  import {
    config,
    removeKeytimesMessage,
    setKeytimesMessageType,
    updateField,
    validationErrors,
  } from '$lib/formStore';

  interface Props {
    buttonIndex: number;
    cycle: 'short' | 'long';
    entryIndex: number;
    slot: 'down' | 'up';
    msgIndex: number;
    message: KeytimesMessage;
    globalChannel: number;
  }

  let { buttonIndex, cycle, entryIndex, slot, msgIndex, message, globalChannel }: Props = $props();

  // Path prefix used for both updateField() and validation error lookups.
  let pathPrefix = $derived(`buttons[${buttonIndex}].${cycle}[${entryIndex}].${slot}[${msgIndex}]`);

  // Display the configured channel as 1-16, fall back to global if undefined.
  // HID messages have no channel field; the channel input is hidden for HID below.
  let messageChannel = $derived(
    message.type !== 'hid' ? (message as { channel?: number }).channel : undefined
  );
  let displayChannel = $derived(
    messageChannel !== undefined ? messageChannel + 1 : undefined
  );
  let effectiveChannel = $derived(
    messageChannel !== undefined ? messageChannel + 1 : globalChannel + 1
  );

  function handleTypeChange(e: Event) {
    const newType = (e.target as HTMLSelectElement).value as MessageType;
    setKeytimesMessageType(buttonIndex, cycle, entryIndex, slot, msgIndex, newType);
  }

  function handleChannelChange(e: Event) {
    const target = e.target as HTMLInputElement;
    if (target.value === '') {
      updateField(`${pathPrefix}.channel`, undefined);
    } else {
      // Convert 1-16 display to 0-15 storage
      updateField(`${pathPrefix}.channel`, parseInt(target.value) - 1);
    }
  }

  function handleIntField(field: string, e: Event) {
    const target = e.target as HTMLInputElement;
    updateField(`${pathPrefix}.${field}`, parseInt(target.value));
  }

  function handleStringField(field: string, e: Event) {
    const target = e.target as HTMLInputElement;
    updateField(`${pathPrefix}.${field}`, target.value === '' ? undefined : target.value);
  }

  function handleRemove() {
    removeKeytimesMessage(buttonIndex, cycle, entryIndex, slot, msgIndex);
  }

  // Page-switch messages carry no MIDI channel; hide the channel input for them.
  let isPageType = $derived(
    message.type === 'page_inc' || message.type === 'page_dec' || message.type === 'page_jump'
  );

  // page_jump target is a 0-based index; name the page it lands on (mirrors
  // ButtonRow's hint). Null when out of range — the error text owns that case.
  let pageCount = $derived(($config.pages ?? []).length);
  let jumpTarget = $derived.by(() => {
    if (message.type !== 'page_jump') return null;
    const idx = message.page ?? 0;
    const target = ($config.pages ?? [])[idx];
    if (!target) return null;
    return target.name ? `“${target.name}”` : `Page ${idx + 1}`;
  });

  // Field error lookups
  function errFor(field: string): string | undefined {
    return $validationErrors.get(`${pathPrefix}.${field}`);
  }
</script>

<div class="kt-message">
  <div class="kt-message-row">
    <label class="inline">
      Type:
      <select value={message.type} onchange={handleTypeChange}>
        {#each Object.entries(MESSAGE_TYPE_LABELS) as [val, label]}
          <option value={val}>{label}</option>
        {/each}
      </select>
    </label>

    {#if message.type === 'cc'}
      <label class="inline">
        CC:
        <input type="number" min="0" max="127"
               value={message.cc}
               oninput={(e) => handleIntField('cc', e)}
               class:error={!!errFor('cc')} />
      </label>
      <label class="inline">
        Value:
        <input type="number" min="0" max="127"
               value={message.value}
               oninput={(e) => handleIntField('value', e)}
               class:error={!!errFor('value')} />
      </label>
    {:else if message.type === 'note'}
      <label class="inline">
        Note:
        <input type="number" min="0" max="127"
               value={message.note}
               oninput={(e) => handleIntField('note', e)}
               class:error={!!errFor('note')} />
      </label>
      <label class="inline">
        Velocity:
        <input type="number" min="0" max="127"
               value={message.velocity}
               oninput={(e) => handleIntField('velocity', e)}
               class:error={!!errFor('velocity')} />
      </label>
    {:else if message.type === 'pc'}
      <label class="inline">
        Program:
        <input type="number" min="0" max="127"
               value={message.program}
               oninput={(e) => handleIntField('program', e)}
               class:error={!!errFor('program')} />
      </label>
    {:else if message.type === 'pc_inc' || message.type === 'pc_dec'}
      <label class="inline">
        Step:
        <input type="number" min="1" max="127"
               value={message.step ?? 1}
               oninput={(e) => handleIntField('step', e)}
               class:error={!!errFor('step')} />
      </label>
    {:else if message.type === 'page_inc' || message.type === 'page_dec'}
      <label class="inline">
        Step:
        <input type="number" min="1"
               value={message.page_step ?? 1}
               oninput={(e) => handleIntField('page_step', e)}
               title="Pages to move per press; wraps at the ends."
               class:error={!!errFor('page_step')} />
      </label>
    {:else if message.type === 'page_jump'}
      <label class="inline">
        Target Page:
        <input type="number" min="0" max={pageCount - 1}
               value={message.page ?? 0}
               oninput={(e) => handleIntField('page', e)}
               title="0-based page index (0 = first page)."
               class:error={!!errFor('page')} />
      </label>
      {#if !errFor('page') && jumpTarget}
        <span class="kt-hint">→ {jumpTarget}</span>
      {/if}
    {:else if message.type === 'hid'}
      <label class="inline">
        Action:
        <select value={message.action ?? 'send'} onchange={(e) => handleStringField('action', e)}>
          <option value="send">send</option>
          <option value="press">press</option>
          <option value="release">release</option>
          <option value="delay">delay</option>
        </select>
      </label>
      {#if message.action !== 'delay'}
        <label class="inline">
          Key:
          <input type="text" placeholder="A, F1, Space, ..."
                 value={message.key ?? ''}
                 oninput={(e) => handleStringField('key', e)} />
        </label>
        <label class="inline">
          Modifier:
          <select value={message.modifier ?? ''} onchange={(e) => handleStringField('modifier', e)}>
            <option value="">(none)</option>
            <option value="ctrl">ctrl</option>
            <option value="shift">shift</option>
            <option value="alt">alt</option>
            <option value="option">option</option>
            <option value="windows">windows</option>
          </select>
        </label>
      {:else}
        <label class="inline">
          Delay ms:
          <input type="number" min="1" max="5000"
                 value={message.delay_ms ?? 50}
                 oninput={(e) => handleIntField('delay_ms', e)} />
        </label>
      {/if}
    {/if}

    {#if message.type !== 'hid' && !isPageType}
      <label class="inline">
        Ch:
        <input type="number" min="1" max="16"
               value={displayChannel ?? ''}
               placeholder={String(globalChannel + 1)}
               oninput={handleChannelChange}
               title="MIDI channel override (1-16). Default: {effectiveChannel}"
               class:error={!!errFor('channel')} />
      </label>
    {/if}

    <button type="button" class="kt-remove" onclick={handleRemove} title="Remove message">×</button>
  </div>
</div>

<style>
  .kt-message {
    padding: 0.25rem 0.5rem;
    margin: 0.25rem 0;
    background: #fafafa;
    border: 1px solid #ddd;
    border-radius: 3px;
  }

  .kt-message-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    align-items: center;
  }

  label.inline {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    font-size: 0.8125rem;
  }

  input[type="number"], select, input[type="text"] {
    padding: 0.125rem 0.25rem;
    border: 1px solid #bbb;
    border-radius: 3px;
    font-size: 0.8125rem;
  }

  input[type="number"] { width: 4rem; }
  input[type="text"] { width: 6rem; }
  select { font-size: 0.8125rem; }

  .kt-hint {
    font-size: 0.75rem;
    color: #666;
    white-space: nowrap;
  }

  input.error {
    border-color: #c00;
    background: #fef0f0;
  }

  .kt-remove {
    padding: 0 0.5rem;
    background: #fee;
    border: 1px solid #d88;
    color: #c00;
    border-radius: 3px;
    cursor: pointer;
    font-weight: bold;
    margin-left: auto;
  }

  .kt-remove:hover {
    background: #fdd;
  }
</style>
