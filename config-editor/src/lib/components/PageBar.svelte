<script lang="ts">
  import {
    config, currentPage, validationErrors,
    setActivePage, addPage, duplicatePage, deletePage, movePage, updatePageField,
    PAGE_CAP,
  } from '$lib/formStore';
  import type { Page } from '$lib/types';

  let renaming = $state(false);
  let renameValue = $state('');
  let renameInput = $state<HTMLInputElement | null>(null);

  let pages = $derived(($config.pages ?? []) as Page[]);
  let activeIndex = $derived(
    pages.length ? Math.max(0, Math.min(pages.length - 1, $config.active_page ?? 0)) : 0
  );
  let nameError = $derived($validationErrors.get('name'));

  $effect(() => {
    if (renaming) renameInput?.focus();
  });

  function pageLabel(name: string | undefined, i: number): string {
    return name ? `${i + 1}: ${name}` : `Page ${i + 1}`;
  }

  function startRename() {
    renameValue = $currentPage?.name ?? '';
    renaming = true;
  }

  function commitRename() {
    if (!renaming) return;
    renaming = false;
    // Trimmed empty string clears the name (normalizeConfig strips it on save).
    updatePageField('name', renameValue.trim());
  }

  function cancelRename() {
    renaming = false;
  }

  function handleRenameKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter') {
      e.preventDefault();
      commitRename();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      cancelRename();
    }
  }
</script>

<div class="page-bar">
  <label for="page-select">Page</label>
  {#if renaming}
    <input
      id="page-select"
      class="rename-input"
      type="text"
      maxlength="24"
      placeholder="Page name"
      bind:this={renameInput}
      bind:value={renameValue}
      onblur={commitRename}
      onkeydown={handleRenameKeydown}
    />
  {:else}
    <select
      id="page-select"
      value={activeIndex}
      onchange={(e) => setActivePage(Number(e.currentTarget.value))}
    >
      {#each pages as page, i (page.__uiId ?? i)}
        <option value={i}>{pageLabel(page.name, i)}</option>
      {/each}
    </select>
  {/if}

  <div class="page-actions">
    <button
      type="button"
      onclick={() => movePage(activeIndex, activeIndex - 1)}
      disabled={renaming || activeIndex === 0}
      title="Move page earlier"
      aria-label="Move page earlier"
    >◀</button>
    <button
      type="button"
      onclick={() => movePage(activeIndex, activeIndex + 1)}
      disabled={renaming || activeIndex >= pages.length - 1}
      title="Move page later"
      aria-label="Move page later"
    >▶</button>
    <button type="button" onclick={addPage} disabled={renaming || pages.length >= PAGE_CAP}>
      Add
    </button>
    <button
      type="button"
      onclick={() => duplicatePage(activeIndex)}
      disabled={renaming || pages.length >= PAGE_CAP}
    >
      Duplicate
    </button>
    <button type="button" onclick={startRename} disabled={renaming}>
      Rename
    </button>
    <button
      type="button"
      onclick={() => deletePage(activeIndex)}
      disabled={renaming || pages.length <= 1}
    >
      Delete
    </button>
  </div>

  {#if nameError}
    <span class="error">{nameError}</span>
  {/if}
</div>

<style>
  .page-bar {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    padding: 10px 12px;
    margin-bottom: 12px;
    background-color: var(--color-bg-secondary);
    border: 1px solid var(--color-border);
    border-radius: 6px;
  }

  label {
    font-size: 13px;
    font-weight: 600;
    color: var(--color-text-secondary);
  }

  select,
  .rename-input {
    padding: 5px 8px;
    font-size: 13px;
    background-color: var(--color-bg);
    color: var(--color-text);
    border: 1px solid var(--color-border);
    border-radius: 4px;
    min-width: 160px;
  }

  .page-actions {
    display: flex;
    gap: 6px;
  }

  .page-actions button {
    padding: 4px 10px;
    font-size: 13px;
    border-radius: 4px;
    border: 1px solid var(--color-border);
    background-color: var(--color-bg);
    color: var(--color-text);
    cursor: pointer;
  }

  .page-actions button:hover:not(:disabled) {
    background-color: var(--color-bg-hover);
  }

  .page-actions button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .error {
    color: var(--error-text, #f48771);
    font-size: 12px;
  }
</style>
