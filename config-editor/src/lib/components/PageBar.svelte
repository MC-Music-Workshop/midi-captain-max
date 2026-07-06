<script lang="ts">
  import { config, validationErrors, setActivePage } from '$lib/formStore';
  import EditPagesModal from './EditPagesModal.svelte';
  import type { Page } from '$lib/types';

  let managing = $state(false);

  let pages = $derived(($config.pages ?? []) as Page[]);
  let activeIndex = $derived(
    pages.length ? Math.max(0, Math.min(pages.length - 1, $config.active_page ?? 0)) : 0
  );
  let nameError = $derived($validationErrors.get('name'));

  function pageLabel(name: string | undefined, i: number): string {
    return name ? `${i + 1}: ${name}` : `Page ${i + 1}`;
  }

  // Field edits commit on blur, but WebKit doesn't blur a focused input when
  // the user clicks a <select> or <button> — so an edit can still be "in
  // flight" when a page operation runs. Force the blur so the edit commits to
  // the page it was typed on BEFORE the operation changes the active page.
  function commitPendingEdit() {
    const el = document.activeElement;
    if (el instanceof HTMLElement) el.blur();
  }

  function handlePageSelect(e: Event & { currentTarget: HTMLSelectElement }) {
    const index = Number(e.currentTarget.value);
    commitPendingEdit();
    setActivePage(index);
  }

  function goTo(index: number) {
    commitPendingEdit();
    setActivePage(index);
  }

  function openManager() {
    commitPendingEdit();
    managing = true;
  }
</script>

<div class="page-bar">
  <label for="page-select">Page</label>
  <select id="page-select" value={activeIndex} onchange={handlePageSelect}>
    {#each pages as page, i (page.__uiId ?? i)}
      <option value={i}>{pageLabel(page.name, i)}</option>
    {/each}
  </select>

  <button
    type="button"
    onclick={() => goTo(activeIndex - 1)}
    disabled={activeIndex === 0}
    title="Previous page"
    aria-label="Previous page"
  >◀</button>
  <button
    type="button"
    onclick={() => goTo(activeIndex + 1)}
    disabled={activeIndex >= pages.length - 1}
    title="Next page"
    aria-label="Next page"
  >▶</button>

  <button type="button" class="edit-pages" onclick={openManager}>
    Edit Pages…
  </button>

  {#if nameError}
    <span class="error">{nameError}</span>
  {/if}
</div>

{#if managing}
  <EditPagesModal onClose={() => (managing = false)} />
{/if}

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

  select {
    padding: 5px 8px;
    font-size: 13px;
    background-color: var(--color-bg);
    color: var(--color-text);
    border: 1px solid var(--color-border);
    border-radius: 4px;
    min-width: 160px;
  }

  button {
    padding: 4px 10px;
    font-size: 13px;
    border-radius: 4px;
    border: 1px solid var(--color-border);
    background-color: var(--color-bg);
    color: var(--color-text);
    cursor: pointer;
  }

  button:hover:not(:disabled) {
    background-color: var(--color-bg-hover);
  }

  button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .edit-pages {
    margin-left: 4px;
  }

  .error {
    color: var(--error-text, #f48771);
    font-size: 12px;
  }
</style>
