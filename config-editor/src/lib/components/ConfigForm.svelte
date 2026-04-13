<script lang="ts">
  import { onMount, type Snippet } from 'svelte';
  import { isDirty, canUndo, canRedo, undo, redo, validationErrors, config } from '$lib/formStore';
  
  interface Props {
    onSave: () => void;
    children: Snippet;
  }
  
  let { onSave, children }: Props = $props();
  
  let hasErrors = $derived($validationErrors.size > 0);
  let showJsonModal = $state(false);
  let jsonText = $state('');

  function handleUndo() {
    undo();
  }

  function handleRedo() {
    redo();
  }

  function handleViewJson() {
    jsonText = JSON.stringify($config, null, 2);
    showJsonModal = true;
  }
  
  function closeJsonModal() {
    showJsonModal = false;
  }
  
  function copyJsonToClipboard() {
    navigator.clipboard.writeText(jsonText);
  }

  function handleSave() {
    onSave();
  }

  // Keyboard shortcuts
  function handleKeydown(event: KeyboardEvent) {
    const isCmd = event.metaKey || event.ctrlKey;

    if (event.key === 'Escape' && showJsonModal) {
      event.preventDefault();
      closeJsonModal();
      return;
    }

    if (isCmd && event.key === 'z') {
      event.preventDefault();
      if (event.shiftKey && $canRedo) {
        handleRedo();
      } else if ($canUndo) {
        handleUndo();
      }
    } else if (isCmd && event.key === 's') {
      event.preventDefault();
      handleSave();
    }
  }

  onMount(() => {
    window.addEventListener('keydown', handleKeydown);
    return () => {
      window.removeEventListener('keydown', handleKeydown);
    };
  });
</script>

<svelte:head>
  <title>Config Form Editor - MIDI Captain</title>
</svelte:head>

<div class="config-form">
  <!-- Toolbar -->
  <div class="toolbar">
    <div class="toolbar-group">
      <button
        class="toolbar-btn"
        disabled={!$canUndo}
        onclick={handleUndo}
        title="Undo (⌘Z)"
      >
        Undo
      </button>
      <button
        class="toolbar-btn"
        disabled={!$canRedo}
        onclick={handleRedo}
        title="Redo (⌘⇧Z)"
      >
        Redo
      </button>
    </div>

    <div class="toolbar-group">
      <button class="toolbar-btn secondary" onclick={handleViewJson}>
        View JSON
      </button>
      <button
        class="toolbar-btn primary"
        disabled={hasErrors}
        onclick={handleSave}
        title="Save (⌘S)"
      >
        {hasErrors ? 'Fix errors to save' : $isDirty ? 'Save to Device *' : 'Save to Device'}
      </button>
    </div>
  </div>

  <!-- Form sections -->
  <div class="form-sections">
    {@render children()}
  </div>
</div>

<!-- JSON Modal. Backdrop click closes; Escape also closes (see handleKeydown). -->
{#if showJsonModal}
  <div
    class="modal-backdrop"
    role="presentation"
    tabindex="-1"
    onclick={closeJsonModal}
    onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') closeJsonModal(); }}
  >
    <div
      class="modal-content"
      role="dialog"
      aria-modal="true"
      aria-labelledby="json-modal-title"
      tabindex="-1"
      onclick={(e) => e.stopPropagation()}
      onkeydown={(e) => e.stopPropagation()}
    >
      <div class="modal-header">
        <h2 id="json-modal-title">Current Configuration (JSON)</h2>
        <button class="close-btn" onclick={closeJsonModal} aria-label="Close">✕</button>
      </div>
      <div class="modal-body">
        <pre class="json-display">{jsonText}</pre>
      </div>
      <div class="modal-footer">
        <button class="toolbar-btn secondary" onclick={copyJsonToClipboard}>Copy to Clipboard</button>
        <button class="toolbar-btn" onclick={closeJsonModal}>Close</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .config-form {
    display: flex;
    flex-direction: column;
    height: 100%;
    background-color: var(--color-bg);
  }

  /* Toolbar */
  .toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    background-color: var(--color-bg-secondary);
    border-bottom: 1px solid var(--color-border);
    gap: 12px;
  }

  .toolbar-group {
    display: flex;
    gap: 8px;
  }

  .toolbar-btn {
    padding: 6px 12px;
    border-radius: 4px;
    border: 1px solid var(--color-border);
    background-color: var(--color-bg);
    color: var(--color-text);
    font-size: 14px;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .toolbar-btn:hover:not(:disabled) {
    background-color: var(--color-bg-hover);
    border-color: var(--color-border-hover);
  }

  .toolbar-btn:active:not(:disabled) {
    transform: translateY(1px);
  }

  .toolbar-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .toolbar-btn.primary {
    background-color: var(--color-primary);
    color: white;
    border-color: var(--color-primary);
  }

  .toolbar-btn.primary:hover:not(:disabled) {
    background-color: var(--color-primary-hover);
    border-color: var(--color-primary-hover);
  }

  .toolbar-btn.secondary {
    background-color: transparent;
  }

  /* Form sections */
  .form-sections {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
  }

  /* JSON Modal */
  .modal-backdrop {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }

  .modal-content {
    background-color: var(--color-bg);
    border-radius: 8px;
    width: 90%;
    max-width: 800px;
    max-height: 80vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
  }

  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 20px;
    border-bottom: 1px solid var(--color-border);
  }

  .modal-header h2 {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
  }

  .close-btn {
    background: none;
    border: none;
    font-size: 24px;
    cursor: pointer;
    padding: 0;
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 4px;
    color: var(--color-text-secondary);
  }

  .close-btn:hover {
    background-color: var(--color-bg-hover);
  }

  .modal-body {
    flex: 1;
    overflow: auto;
    padding: 20px;
  }

  .json-display {
    background-color: var(--color-bg-secondary);
    border: 1px solid var(--color-border);
    border-radius: 4px;
    padding: 16px;
    font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
    font-size: 13px;
    line-height: 1.5;
    overflow-x: auto;
    margin: 0;
    white-space: pre;
    color: var(--color-text);
  }

  .modal-footer {
    display: flex;
    justify-content: flex-end;
    gap: 12px;
    padding: 16px 20px;
    border-top: 1px solid var(--color-border);
  }

  /* CSS Variables (will inherit from app theme) */
  :root {
    --color-bg: #1e1e1e;
    --color-bg-secondary: #252526;
    --color-bg-hover: #2a2d2e;
    --color-text: #cccccc;
    --color-text-secondary: #808080;
    --color-border: #3e3e42;
    --color-border-hover: #555555;
    --color-primary: #0e639c;
    --color-primary-hover: #1177bb;
  }
</style>
