<script lang="ts">
  import {
    config, setActivePage, addPage, duplicatePage, deletePage, movePage,
    updatePageField, PAGE_CAP,
  } from '$lib/formStore';
  import type { Page } from '$lib/types';

  let { onClose }: { onClose: () => void } = $props();

  let pages = $derived(($config.pages ?? []) as Page[]);
  // Selection IS the active page: clicking a row switches the form behind the
  // modal, and every action button targets the active page — so the existing
  // store helpers apply unchanged and each op stays one undo step.
  let activeIndex = $derived(
    pages.length ? Math.max(0, Math.min(pages.length - 1, $config.active_page ?? 0)) : 0
  );

  let renamingIndex = $state<number | null>(null);
  let renameValue = $state('');
  let renameInput = $state<HTMLInputElement | null>(null);

  $effect(() => {
    if (renamingIndex !== null) renameInput?.focus();
  });

  function startRename(i: number) {
    renameValue = pages[i]?.name ?? '';
    renamingIndex = i;
  }

  function commitRename() {
    if (renamingIndex === null) return;
    renamingIndex = null;
    // The double-click that started the rename also selected the row, so the
    // active page is the renamed one. Trimmed empty clears the name.
    updatePageField('name', renameValue.trim());
  }

  function cancelRename() {
    renamingIndex = null;
  }

  function handleRenameKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter') {
      e.preventDefault();
      commitRename();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation(); // don't let the same press also close the modal
      cancelRename();
    }
  }

  function handleWindowKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      e.preventDefault();
      onClose();
    }
  }
</script>

<svelte:window onkeydown={handleWindowKeydown} />

<!-- Backdrop click closes; Escape also closes (see handleWindowKeydown). -->
<div
  class="modal-backdrop"
  role="presentation"
  tabindex="-1"
  onclick={onClose}
  onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') onClose(); }}
>
  <div
    class="modal-content"
    role="dialog"
    aria-modal="true"
    aria-label="Edit Pages"
    tabindex="-1"
    onclick={(e) => e.stopPropagation()}
    onkeydown={(e) => e.stopPropagation()}
  >
    <div class="modal-header">
      <h2>Edit Pages</h2>
      <button class="close-btn" onclick={onClose} aria-label="Close">✕</button>
    </div>

    <ul class="page-list">
      {#each pages as page, i (page.__uiId ?? i)}
        <li>
          {#if renamingIndex === i}
            <input
              class="rename-input"
              type="text"
              maxlength="24"
              placeholder="Page name"
              aria-label="Page name"
              bind:this={renameInput}
              bind:value={renameValue}
              onblur={commitRename}
              onkeydown={handleRenameKeydown}
            />
          {:else}
            <button
              type="button"
              class="page-row"
              aria-current={i === activeIndex ? 'true' : undefined}
              title="Double-click to rename"
              onclick={() => setActivePage(i)}
              ondblclick={() => startRename(i)}
            >
              <span class="row-num">{i + 1}</span>
              <span class="row-name">{page.name ?? ''}</span>
            </button>
          {/if}
        </li>
      {/each}
    </ul>

    <div class="modal-footer">
      <div class="row-actions">
        <button
          onclick={addPage}
          disabled={pages.length >= PAGE_CAP}
          title="Add page"
          aria-label="Add page"
        >+</button>
        <button
          onclick={() => deletePage(activeIndex)}
          disabled={pages.length <= 1}
          title="Delete page"
          aria-label="Delete page"
        >−</button>
        <button
          onclick={() => duplicatePage(activeIndex)}
          disabled={pages.length >= PAGE_CAP}
          title="Duplicate page"
          aria-label="Duplicate page"
        >Duplicate</button>
        <button
          onclick={() => movePage(activeIndex, activeIndex - 1)}
          disabled={activeIndex === 0}
          title="Move page up"
          aria-label="Move page up"
        >↑</button>
        <button
          onclick={() => movePage(activeIndex, activeIndex + 1)}
          disabled={activeIndex >= pages.length - 1}
          title="Move page down"
          aria-label="Move page down"
        >↓</button>
      </div>
      <button class="done-btn" onclick={onClose}>Done</button>
    </div>
  </div>
</div>

<style>
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
    max-width: 420px;
    max-height: 70vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
  }

  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 14px 18px;
    border-bottom: 1px solid var(--color-border);
  }

  .modal-header h2 {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
  }

  .close-btn {
    background: none;
    border: none;
    font-size: 20px;
    cursor: pointer;
    padding: 0;
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 4px;
    color: var(--color-text-secondary);
  }

  .close-btn:hover {
    background-color: var(--color-bg-hover);
  }

  .page-list {
    list-style: none;
    margin: 0;
    padding: 8px;
    overflow-y: auto;
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .page-row,
  .rename-input {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    padding: 7px 10px;
    font-size: 13px;
    text-align: left;
    background-color: var(--color-bg);
    color: var(--color-text);
    border: 1px solid transparent;
    border-radius: 4px;
    cursor: pointer;
  }

  .page-row:hover {
    background-color: var(--color-bg-hover);
  }

  .page-row[aria-current='true'] {
    background-color: var(--color-primary);
    color: white;
  }

  .row-num {
    min-width: 1.5em;
    opacity: 0.7;
  }

  .rename-input {
    border-color: var(--color-border);
    cursor: text;
  }

  .modal-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    padding: 12px 18px;
    border-top: 1px solid var(--color-border);
  }

  .row-actions {
    display: flex;
    gap: 6px;
  }

  .modal-footer button {
    padding: 4px 10px;
    font-size: 13px;
    border-radius: 4px;
    border: 1px solid var(--color-border);
    background-color: var(--color-bg);
    color: var(--color-text);
    cursor: pointer;
  }

  .row-actions button {
    min-width: 32px;
  }

  .modal-footer button:hover:not(:disabled) {
    background-color: var(--color-bg-hover);
  }

  .modal-footer button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .done-btn {
    background-color: var(--color-primary);
    color: white;
    border-color: var(--color-primary);
  }
</style>
