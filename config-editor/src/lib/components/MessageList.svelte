<script lang="ts">
  import MessageEditor from './MessageEditor.svelte';
  import type { KeytimesMessage } from '$lib/types';
  import { addMessage } from '$lib/formStore';

  // One editable list of messages: a keytimes entry's down/up slot, or a
  // button's messages_on/messages_off.
  interface Props {
    buttonIndex: number;
    // Button-relative path of the list: "short[0].down", "messages_on".
    listPath: string;
    label: string;
    messages: KeytimesMessage[];
    globalChannel: number;
    emptyHint: string;
    title?: string;
    // Render the label as code (keytimes event names like short_down).
    mono?: boolean;
    sharedCcStep?: boolean;
  }

  let { buttonIndex, listPath, label, messages, globalChannel, emptyHint, title, mono = false,
        sharedCcStep = true }: Props = $props();
</script>

<div class="kt-slot">
  <div class="kt-slot-header" {title}>
    <span class="kt-slot-label" class:mono>{label}</span>
    <button type="button" class="kt-add-msg" onclick={() => addMessage(buttonIndex, listPath)}>
      + message
    </button>
    {#if messages.length === 0}
      <span class="kt-slot-empty-hint">{emptyHint}</span>
    {/if}
  </div>
  {#each messages as msg, mi ((msg as { __uiId?: number }).__uiId ?? mi)}
    <MessageEditor
      {buttonIndex}
      {listPath}
      msgIndex={mi}
      message={msg}
      {globalChannel}
      {sharedCcStep}
    />
  {/each}
</div>

<style>
  .kt-slot {
    margin: 0.25rem 0 0.25rem 0.5rem;
    padding: 0.25rem;
    border-left: 2px solid #cde;
    padding-left: 0.5rem;
  }

  .kt-slot-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.25rem;
  }

  .kt-slot-label {
    font-size: 0.8125rem;
    color: #555;
  }

  .kt-slot-label.mono {
    font-family: monospace;
  }

  .kt-slot-empty-hint {
    font-size: 0.75rem;
    color: #999;
    font-style: italic;
  }

  .kt-add-msg {
    padding: 0.125rem 0.4rem;
    background: #f0f0f0;
    border: 1px solid #bbb;
    border-radius: 3px;
    cursor: pointer;
    font-size: 0.75rem;
  }

  .kt-add-msg:hover {
    background: #e0e0e0;
  }
</style>
