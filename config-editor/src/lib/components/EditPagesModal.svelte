<script lang="ts">
  import { save, open, message } from '@tauri-apps/plugin-dialog';
  import {
    config, setActivePage, addPage, duplicatePage, deletePage, movePage,
    updatePageField, PAGE_CAP, activePageForExport, addPageFromTemplate,
  } from '$lib/formStore';
  import {
    exportPageTemplate, importPageTemplate, listPageTemplates,
    pageTemplatesDir, type TemplateInfo,
  } from '$lib/api';
  import type { Page } from '$lib/types';

  let { onClose }: { onClose: () => void } = $props();

  let picking = $state(false);
  let templates = $state<TemplateInfo[]>([]);

  // `commitPendingEdit` is NOT exported from PageBar.svelte (it's a private
  // helper there) — this modal needs its own copy of the same one-liner so a
  // field mid-edit (e.g. a typed-but-not-yet-blurred channel value) commits
  // before export/insert reads the page.
  function commitPendingEdit() {
    const el = document.activeElement;
    if (el instanceof HTMLElement) el.blur();
  }

  async function saveAsTemplate() {
    commitPendingEdit();
    const page = activePageForExport();
    const dir = await pageTemplatesDir();
    const suggested = (page.name || `Page ${activeIndex + 1}`).replace(/[^\w -]/g, '_');
    const path = await save({
      title: 'Save page as template',
      defaultPath: `${dir}/${suggested}.json`,
      filters: [{ name: 'Page template', extensions: ['json'] }],
    });
    if (!path) return; // user cancelled
    try {
      await exportPageTemplate(path, page);
    } catch (e) {
      await message(String((e as { message?: string })?.message ?? e), { title: 'Export failed', kind: 'error' });
    }
  }

  async function openTemplatePicker() {
    commitPendingEdit();
    templates = await listPageTemplates().catch(() => []);
    picking = true;
  }

  async function addFrom(path: string) {
    picking = false;
    try {
      // Shape-checked in Rust; a bad jump target (or other value) still imports
      // and gets flagged in-editor, so the page always lands.
      const page = await importPageTemplate(path, $config.device);
      addPageFromTemplate(page);
    } catch (e) {
      const err = e as { message?: string; details?: string[] };
      const detail = err?.details?.length ? `\n\n${err.details.join('\n')}` : '';
      await message(`${err?.message ?? e}${detail}`, { title: 'Import failed', kind: 'error' });
    }
  }

  async function browseForTemplate() {
    const dir = await pageTemplatesDir();
    const path = await open({
      title: 'Add page from template',
      defaultPath: dir,
      multiple: false,
      filters: [{ name: 'Page template', extensions: ['json'] }],
    });
    if (typeof path === 'string') await addFrom(path);
  }

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
          onclick={() => startRename(activeIndex)}
          disabled={renamingIndex !== null}
          title="Rename page"
          aria-label="Rename page"
        >Rename</button>
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
        <button onclick={saveAsTemplate} title="Save this page as a template">Save as template…</button>
        <button
          onclick={openTemplatePicker}
          disabled={pages.length >= PAGE_CAP}
          title="Add a page from a template"
        >Add from template…</button>
      </div>
      <button class="done-btn" onclick={onClose}>Done</button>
    </div>

    {#if picking}
      <div class="template-picker">
        <div class="tp-header">
          <span>Choose a template</span>
          <button class="tp-close" onclick={() => (picking = false)} aria-label="Cancel">✕</button>
        </div>
        {#if templates.length}
          <ul class="tp-list">
            {#each templates as t (t.path)}
              <li><button type="button" onclick={() => addFrom(t.path)}>{t.name}</button></li>
            {/each}
          </ul>
        {:else}
          <p class="tp-empty">No saved templates yet.</p>
        {/if}
        <button class="tp-browse" onclick={browseForTemplate}>Browse…</button>
      </div>
    {/if}
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
    /* Flex items default to min-width: auto, so without this the footer's
       row of buttons (now 8, since P4d added two) can force the modal wider
       than max-width instead of wrapping. */
    min-width: 0;
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
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
    padding: 12px 18px;
    border-top: 1px solid var(--color-border);
  }

  .row-actions {
    display: flex;
    flex-wrap: wrap;
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
    align-self: flex-end;
    background-color: var(--color-primary);
    color: white;
    border-color: var(--color-primary);
  }

  .template-picker {
    border-top: 1px solid var(--color-border);
    padding: 12px 18px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .tp-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 13px;
    font-weight: 600;
  }

  .tp-close {
    background: none;
    border: none;
    cursor: pointer;
    color: var(--color-text-secondary);
    font-size: 14px;
  }

  .tp-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
    max-height: 160px;
    overflow-y: auto;
  }

  .tp-list button {
    width: 100%;
    text-align: left;
    padding: 6px 10px;
    font-size: 13px;
    background-color: var(--color-bg);
    color: var(--color-text);
    border: 1px solid var(--color-border);
    border-radius: 4px;
    cursor: pointer;
  }

  .tp-list button:hover {
    background-color: var(--color-bg-hover);
  }

  .tp-empty {
    font-size: 13px;
    color: var(--color-text-secondary);
    margin: 0;
  }

  .tp-browse {
    align-self: flex-start;
    padding: 4px 10px;
    font-size: 13px;
    border-radius: 4px;
    border: 1px solid var(--color-border);
    background-color: var(--color-bg);
    color: var(--color-text);
    cursor: pointer;
  }

  .tp-browse:hover {
    background-color: var(--color-bg-hover);
  }
</style>
