<script lang="ts">
  // Assistant panel (#230): describe a change, it edits the open config as
  // unsaved edits. Non-modal on purpose: the form stays visible and usable so
  // the user can see what changed, undo it, and save it themselves.
  import { onMount, tick } from 'svelte';
  import type Anthropic from '@anthropic-ai/sdk';
  import { createClient, sendTurn, describeError, type ToolOutcome } from '$lib/agent';
  import { agentKeyGet, agentKeySet, agentKeyDelete } from '$lib/api';

  interface Props {
    onClose: () => void;
  }
  let { onClose }: Props = $props();

  // Until the hosted proxy exists the assistant runs on the user's own key. It
  // lives in the OS keychain (secrets.rs); this component only holds it in memory.
  // Early builds kept it in localStorage under this name; onMount moves it out.
  const LEGACY_KEY_STORAGE = 'mcm.agentApiKey';

  function takeLegacyKey(): string {
    try {
      const key = globalThis.localStorage?.getItem(LEGACY_KEY_STORAGE) ?? '';
      globalThis.localStorage?.removeItem(LEGACY_KEY_STORAGE);
      return key;
    } catch {
      return '';
    }
  }

  type Entry = { kind: 'user' | 'assistant' | 'note' | 'error'; text: string };

  let apiKey = $state('');
  let keyLoading = $state(true);
  // Set when the keychain can't be used: the key then lasts until the app closes.
  let keyNotice = $state('');
  let keyDraft = $state('');
  let input = $state('');
  let busy = $state(false);
  let entries = $state<Entry[]>([]);
  let log: HTMLDivElement | undefined = $state();

  // Not reactive: the API conversation, including tool calls the panel doesn't show.
  const history: Anthropic.MessageParam[] = [];
  let abort: AbortController | null = null;

  async function storeKey(key: string) {
    apiKey = key;
    try {
      await agentKeySet(key);
      keyNotice = '';
    } catch (e) {
      keyNotice = `${describeError(e)} The key will be forgotten when the app closes.`;
    }
  }

  onMount(async () => {
    const legacy = takeLegacyKey();
    try {
      const stored = await agentKeyGet();
      if (stored) apiKey = stored;
      else if (legacy) await storeKey(legacy);
    } catch (e) {
      keyNotice = describeError(e);
      if (legacy) apiKey = legacy;
    } finally {
      keyLoading = false;
    }
  });

  async function saveKey() {
    const key = keyDraft.trim();
    if (!key) return;
    keyDraft = '';
    await storeKey(key);
  }

  async function forgetKey() {
    apiKey = '';
    try {
      await agentKeyDelete();
      keyNotice = '';
    } catch (e) {
      keyNotice = describeError(e);
    }
  }

  async function scrollToEnd() {
    await tick();
    log?.scrollTo({ top: log.scrollHeight });
  }

  function add(entry: Entry) {
    entries.push(entry);
    scrollToEnd();
  }

  function onText(delta: string) {
    const last = entries[entries.length - 1];
    if (last?.kind === 'assistant') last.text += delta;
    else entries.push({ kind: 'assistant', text: delta });
    scrollToEnd();
  }

  function onTool(name: string, outcome: ToolOutcome) {
    if (outcome.applied) add({ kind: 'note', text: 'Config changed. Review it, then save. Undo reverts it.' });
    else if (name === 'apply_changes') add({ kind: 'note', text: 'A change was rejected by validation; retrying.' });
  }

  async function send() {
    const text = input.trim();
    if (!text || busy || !apiKey) return;
    input = '';
    busy = true;
    add({ kind: 'user', text });
    abort = new AbortController();
    try {
      await sendTurn(createClient(apiKey), history, text, { onText, onTool }, abort.signal);
    } catch (e) {
      add({ kind: 'error', text: describeError(e) });
    } finally {
      busy = false;
      abort = null;
    }
  }

  function handleKeydown(event: KeyboardEvent) {
    // Enter sends; Shift+Enter makes a new line.
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      send();
    }
  }
</script>

<aside class="agent-panel" aria-label="Assistant">
  <div class="agent-header">
    <h2>Assistant</h2>
    <button class="icon-btn" onclick={onClose} aria-label="Close assistant">✕</button>
  </div>

  {#if keyNotice}<p class="hint notice" role="status">{keyNotice}</p>{/if}

  {#if keyLoading}
    <p class="hint notice">Loading…</p>
  {:else if !apiKey}
    <form class="key-form" onsubmit={(e) => { e.preventDefault(); saveKey(); }}>
      <label for="agent-api-key">Anthropic API key</label>
      <input id="agent-api-key" type="password" autocomplete="off" placeholder="sk-ant-…" bind:value={keyDraft} />
      <button class="send-btn" type="submit" disabled={!keyDraft.trim()}>Use this key</button>
      <p class="hint">
        The assistant runs on your own Anthropic API key and you pay for its usage. The key is stored in this
        computer's keychain. Your config is sent to Anthropic with each request.
      </p>
    </form>
  {:else}
    <div class="agent-log" bind:this={log} aria-live="polite">
      {#if entries.length === 0}
        <p class="hint">
          Describe a change, for example: “Switch 3 toggles CC 52 on channel 1, red when on.” The change appears in
          the editor as unsaved edits for you to review and save.
        </p>
      {/if}
      {#each entries as entry, i (i)}
        <div class="entry {entry.kind}">{entry.text}</div>
      {/each}
      {#if busy}<div class="entry note">Working…</div>{/if}
    </div>

    <div class="agent-input">
      <label class="visually-hidden" for="agent-input">Describe a change</label>
      <textarea
        id="agent-input"
        rows="3"
        placeholder="Describe a change…"
        bind:value={input}
        onkeydown={handleKeydown}
        disabled={busy}
      ></textarea>
      <div class="agent-actions">
        <button class="link-btn" onclick={forgetKey} disabled={busy}>Change API key</button>
        {#if busy}
          <button class="send-btn" onclick={() => abort?.abort()}>Stop</button>
        {:else}
          <button class="send-btn" onclick={send} disabled={!input.trim()}>Send</button>
        {/if}
      </div>
    </div>
  {/if}
</aside>

<style>
  .agent-panel {
    position: fixed;
    top: 0;
    right: 0;
    bottom: 0;
    width: min(380px, 90vw);
    display: flex;
    flex-direction: column;
    background: var(--bg-secondary, #2d2d2d);
    color: var(--text-primary, #d4d4d4);
    border-left: 1px solid var(--border-color, #404040);
    box-shadow: -4px 0 16px rgba(0, 0, 0, 0.3);
    z-index: 900;
  }

  .agent-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 12px;
    border-bottom: 1px solid var(--border-color, #404040);
  }

  .agent-header h2 {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
  }

  .icon-btn,
  .link-btn {
    background: none;
    border: none;
    color: var(--text-secondary, #888888);
    cursor: pointer;
    font-size: 12px;
  }

  .icon-btn:hover,
  .link-btn:hover:not(:disabled) {
    color: var(--text-primary, #d4d4d4);
  }

  .agent-log {
    flex: 1;
    overflow-y: auto;
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .entry {
    padding: 8px 10px;
    border-radius: 6px;
    font-size: 13px;
    line-height: 1.4;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }

  .entry.user {
    align-self: flex-end;
    max-width: 90%;
    background: var(--accent, #0078d4);
    color: #ffffff;
  }

  .entry.assistant {
    background: var(--bg-tertiary, #3c3c3c);
  }

  .entry.note {
    padding: 2px 4px;
    font-size: 12px;
    color: var(--text-secondary, #888888);
  }

  .entry.error {
    background: var(--error-bg, #3c1f1f);
    border: 1px solid var(--error-border, #5c2f2f);
    color: var(--error-text, #f48771);
  }

  .hint {
    margin: 0;
    font-size: 12px;
    line-height: 1.4;
    color: var(--text-secondary, #888888);
  }

  .hint.notice {
    padding: 8px 12px;
  }

  .key-form,
  .agent-input {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 12px;
  }

  .agent-input {
    border-top: 1px solid var(--border-color, #404040);
  }

  .key-form label {
    font-size: 12px;
    font-weight: 600;
  }

  .key-form input,
  .agent-input textarea {
    padding: 8px;
    border: 1px solid var(--border-color, #404040);
    border-radius: 4px;
    background: var(--bg-primary, #1e1e1e);
    color: var(--text-primary, #d4d4d4);
    font: inherit;
    font-size: 13px;
    resize: vertical;
  }

  .agent-actions {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .send-btn {
    padding: 6px 14px;
    border: none;
    border-radius: 4px;
    background: var(--accent, #0078d4);
    color: #ffffff;
    font-size: 13px;
    cursor: pointer;
  }

  .send-btn:hover:not(:disabled) {
    background: var(--accent-hover, #1084d8);
  }

  .send-btn:disabled,
  .link-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .visually-hidden {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip-path: inset(50%);
    white-space: nowrap;
  }
</style>
