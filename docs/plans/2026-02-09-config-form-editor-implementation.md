# Config Form Editor Implementation Plan

**Status:** Shipped — the form editor is the current editor UI.
> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace JSON text editor with visual form UI featuring dropdowns, toggles, text fields, undo/redo, and device-specific handling.

**Architecture:** Svelte 5 components with centralized `formStore` for state management, history tracking for undo/redo, real-time validation with inline errors, device-specific data preservation when switching between Mini6 and STD10.

**Tech Stack:** Svelte 5, TypeScript, Tauri v2, writable stores for reactive state

---

## Phase 1: Form Store Foundation

### Task 1.1: Create Form Store Types

**Files:**
- Create: `config-editor/src/lib/formStore.ts`

**Step 1: Add FormState interface**

Add to top of `formStore.ts`:

```typescript
import { writable, derived, get } from 'svelte/store';
import type { MidiCaptainConfig, ButtonConfig, EncoderConfig, DeviceType } from './types';

interface FormState {
  config: MidiCaptainConfig;
  history: MidiCaptainConfig[];
  historyIndex: number;
  validationErrors: Map<string, string>;
  isDirty: boolean;
  _hiddenButtons?: ButtonConfig[];
  _hiddenEncoder?: EncoderConfig;
}

const HISTORY_LIMIT = 50;
const DEBOUNCE_MS = 500;
```

Expected: File created with types defined

**Step 2: Create initial state**

Add below types:

```typescript
const initialState: FormState = {
  config: {
    device: 'std10',
    buttons: [],
    encoder: undefined,
    expression: undefined,
  },
  history: [],
  historyIndex: -1,
  validationErrors: new Map(),
  isDirty: false,
};

const formState = writable<FormState>(initialState);
```

Expected: Store initialized

**Step 3: Export store and helper**

Add at bottom:

```typescript
export const config = derived(formState, $state => $state.config);
export const isDirty = derived(formState, $state => $state.isDirty);
export const validationErrors = derived(formState, $state => $state.validationErrors);
export const canUndo = derived(formState, $state => $state.historyIndex > 0);
export const canRedo = derived(formState, $state => 
  $state.historyIndex < $state.history.length - 1
);
```

Expected: Derived stores exported

**Step 4: Commit**

```bash
git add config-editor/src/lib/formStore.ts
git commit -m "feat(store): add form store types and initial state"
```

---

### Task 1.2: Implement Load and History Operations

**Files:**
- Modify: `config-editor/src/lib/formStore.ts`

**Step 1: Add loadConfig function**

Add after store creation:

```typescript
let debounceTimer: ReturnType<typeof setTimeout> | null = null;

export function loadConfig(newConfig: MidiCaptainConfig) {
  formState.update(state => ({
    config: structuredClone(newConfig),
    history: [structuredClone(newConfig)],
    historyIndex: 0,
    validationErrors: new Map(),
    isDirty: false,
  }));
}
```

Expected: Load function defined

**Step 2: Add pushHistory helper**

Add below loadConfig:

```typescript
function pushHistory(state: FormState): FormState {
  // Clear any future history if we're not at the end
  const newHistory = state.history.slice(0, state.historyIndex + 1);
  
  // Add current config to history
  newHistory.push(structuredClone(state.config));
  
  // Limit history size
  if (newHistory.length > HISTORY_LIMIT) {
    newHistory.shift();
  }
  
  return {
    ...state,
    history: newHistory,
    historyIndex: newHistory.length - 1,
    isDirty: true,
  };
}
```

Expected: History helper added

**Step 3: Add undo/redo functions**

Add below pushHistory:

```typescript
export function undo() {
  formState.update(state => {
    if (state.historyIndex <= 0) return state;
    
    const newIndex = state.historyIndex - 1;
    return {
      ...state,
      config: structuredClone(state.history[newIndex]),
      historyIndex: newIndex,
      isDirty: newIndex !== 0,
    };
  });
}

export function redo() {
  formState.update(state => {
    if (state.historyIndex >= state.history.length - 1) return state;
    
    const newIndex = state.historyIndex + 1;
    return {
      ...state,
      config: structuredClone(state.history[newIndex]),
      historyIndex: newIndex,
      isDirty: true,
    };
  });
}
```

Expected: Undo/redo functions added

**Step 4: Commit**

```bash
git add config-editor/src/lib/formStore.ts
git commit -m "feat(store): add load, undo, redo operations"
```

---

### Task 1.3: Implement Field Update with Debouncing

**Files:**
- Modify: `config-editor/src/lib/formStore.ts`

**Step 1: Add updateField function**

Add after undo/redo:

```typescript
export function updateField(path: string, value: any) {
  // Clear existing debounce
  if (debounceTimer) {
    clearTimeout(debounceTimer);
  }
  
  // Update value immediately
  formState.update(state => {
    const newConfig = structuredClone(state.config);
    setNestedValue(newConfig, path, value);
    
    return {
      ...state,
      config: newConfig,
      isDirty: true,
    };
  });
  
  // Debounce history push
  debounceTimer = setTimeout(() => {
    formState.update(state => pushHistory(state));
  }, DEBOUNCE_MS);
}
```

Expected: Update function with debounce

**Step 2: Add setNestedValue helper**

Add above updateField:

```typescript
function setNestedValue(obj: any, path: string, value: any) {
  const parts = path.split('.');
  let current = obj;
  
  for (let i = 0; i < parts.length - 1; i++) {
    const part = parts[i];
    const arrayMatch = part.match(/(\w+)\[(\d+)\]/);
    
    if (arrayMatch) {
      const [, key, index] = arrayMatch;
      current = current[key][parseInt(index)];
    } else {
      current = current[part];
    }
  }
  
  const lastPart = parts[parts.length - 1];
  const arrayMatch = lastPart.match(/(\w+)\[(\d+)\]/);
  
  if (arrayMatch) {
    const [, key, index] = arrayMatch;
    current[key][parseInt(index)] = value;
  } else {
    current[lastPart] = value;
  }
}
```

Expected: Helper for nested updates

**Step 3: Commit**

```bash
git add config-editor/src/lib/formStore.ts
git commit -m "feat(store): add field update with debounced history"
```

---

### Task 1.4: Implement Device Type Switching with Preservation

**Files:**
- Modify: `config-editor/src/lib/formStore.ts`

**Step 1: Add setDevice function**

Add after updateField:

```typescript
export function setDevice(deviceType: DeviceType) {
  formState.update(state => {
    const newState = { ...state };
    const currentDevice = state.config.device;
    
    // Switching TO Mini6: preserve STD10-only features
    if (deviceType === 'mini6' && currentDevice === 'std10') {
      // Preserve buttons 7-10
      if (state.config.buttons.length > 6) {
        newState._hiddenButtons = state.config.buttons.slice(6);
      }
      
      // Preserve encoder config
      if (state.config.encoder?.enabled) {
        newState._hiddenEncoder = structuredClone(state.config.encoder);
      }
      
      // Truncate buttons array and disable encoder
      newState.config = {
        ...state.config,
        device: 'mini6',
        buttons: state.config.buttons.slice(0, 6),
        encoder: state.config.encoder ? { ...state.config.encoder, enabled: false } : undefined,
      };
    }
    
    // Switching TO STD10: restore preserved features
    else if (deviceType === 'std10' && currentDevice === 'mini6') {
      newState.config = {
        ...state.config,
        device: 'std10',
        buttons: [
          ...state.config.buttons,
          ...(state._hiddenButtons || createDefaultButtons(7, 10)),
        ],
        encoder: state._hiddenEncoder || state.config.encoder,
      };
      
      // Clear preserved data
      delete newState._hiddenButtons;
      delete newState._hiddenEncoder;
    }
    
    // Same device: no-op
    else {
      newState.config = { ...state.config, device: deviceType };
    }
    
    return pushHistory(newState);
  });
}
```

Expected: Device switching with preservation

**Step 2: Add createDefaultButtons helper**

Add above setDevice:

```typescript
function createDefaultButtons(startIndex: number, endIndex: number): ButtonConfig[] {
  const defaults: ButtonConfig[] = [];
  for (let i = startIndex; i <= endIndex; i++) {
    defaults.push({
      label: `BTN${i}`,
      cc: 20 + i,
      color: 'white',
      mode: 'toggle',
      off_mode: 'dim',
    });
  }
  return defaults;
}
```

Expected: Helper for default buttons

**Step 3: Commit**

```bash
git add config-editor/src/lib/formStore.ts
git commit -m "feat(store): add device switching with data preservation"
```

---

## Phase 2: Validation System

### Task 2.1: Create Validation Types and Rules

**Files:**
- Create: `config-editor/src/lib/validation.ts`

**Step 1: Add validation types**

Create file with:

```typescript
import type { MidiCaptainConfig } from './types';

export interface ValidationResult {
  isValid: boolean;
  errors: Map<string, string>;
}

export interface FieldValidator {
  (value: any, config?: MidiCaptainConfig): string | null;
}
```

Expected: Types defined

**Step 2: Add field validators**

Add below types:

```typescript
export const validators = {
  label: (value: string): string | null => {
    if (!value || value.trim() === '') {
      return 'Label is required';
    }
    if (value.length > 6) {
      return 'Label must be 6 characters or less';
    }
    if (!/^[\w\s-]+$/.test(value)) {
      return 'Label contains invalid characters';
    }
    return null;
  },
  
  cc: (value: number, config?: MidiCaptainConfig): string | null => {
    if (value < 0 || value > 127) {
      return 'CC must be between 0 and 127';
    }
    if (!Number.isInteger(value)) {
      return 'CC must be an integer';
    }
    return null;
  },
  
  range: (min: number, max: number): string | null => {
    if (min >= max) {
      return 'Min must be less than max';
    }
    return null;
  },
  
  withinRange: (value: number, min: number, max: number): string | null => {
    if (value < min || value > max) {
      return `Value must be between ${min} and ${max}`;
    }
    return null;
  },
};
```

Expected: Field validators added

**Step 3: Commit**

```bash
git add config-editor/src/lib/validation.ts
git commit -m "feat(validation): add field validators"
```

---

### Task 2.2: Add Form-Level Validation

**Files:**
- Modify: `config-editor/src/lib/validation.ts`

**Step 1: Add duplicate CC detection**

Add after field validators:

```typescript
export function findDuplicateCC(config: MidiCaptainConfig): Map<string, string> {
  const errors = new Map<string, string>();
  const ccMap = new Map<number, string[]>();
  
  // Collect all CCs with their paths
  config.buttons.forEach((btn, idx) => {
    if (btn.cc !== undefined) {
      const path = `buttons[${idx}].cc`;
      if (!ccMap.has(btn.cc)) {
        ccMap.set(btn.cc, []);
      }
      ccMap.get(btn.cc)!.push(path);
    }
  });
  
  if (config.encoder?.enabled && config.encoder.cc !== undefined) {
    const path = 'encoder.cc';
    if (!ccMap.has(config.encoder.cc)) {
      ccMap.set(config.encoder.cc, []);
    }
    ccMap.get(config.encoder.cc)!.push(path);
  }
  
  if (config.encoder?.push?.enabled && config.encoder.push.cc !== undefined) {
    const path = 'encoder.push.cc';
    if (!ccMap.has(config.encoder.push.cc)) {
      ccMap.set(config.encoder.push.cc, []);
    }
    ccMap.get(config.encoder.push.cc)!.push(path);
  }
  
  if (config.expression?.exp1?.enabled && config.expression.exp1.cc !== undefined) {
    const path = 'expression.exp1.cc';
    if (!ccMap.has(config.expression.exp1.cc)) {
      ccMap.set(config.expression.exp1.cc, []);
    }
    ccMap.get(config.expression.exp1.cc)!.push(path);
  }
  
  if (config.expression?.exp2?.enabled && config.expression.exp2.cc !== undefined) {
    const path = 'expression.exp2.cc';
    if (!ccMap.has(config.expression.exp2.cc)) {
      ccMap.set(config.expression.exp2.cc, []);
    }
    ccMap.get(config.expression.exp2.cc)!.push(path);
  }
  
  // Mark duplicates
  ccMap.forEach((paths, cc) => {
    if (paths.length > 1) {
      paths.forEach(path => {
        const others = paths.filter(p => p !== path).join(', ');
        errors.set(path, `CC ${cc} is also used by: ${others}`);
      });
    }
  });
  
  return errors;
}
```

Expected: Duplicate detection added

**Step 2: Add validateConfig function**

Add after findDuplicateCC:

```typescript
export function validateConfig(config: MidiCaptainConfig): ValidationResult {
  const errors = new Map<string, string>();
  
  // Device-specific validation
  if (config.device === 'mini6') {
    if (config.buttons.length > 6) {
      errors.set('device', 'Mini6 supports only 6 buttons');
    }
    if (config.encoder?.enabled) {
      errors.set('encoder.enabled', 'Mini6 does not support encoder');
    }
  } else if (config.device === 'std10') {
    if (config.buttons.length > 10) {
      errors.set('device', 'STD10 supports only 10 buttons');
    }
  }
  
  // Validate all buttons
  config.buttons.forEach((btn, idx) => {
    const labelError = validators.label(btn.label);
    if (labelError) {
      errors.set(`buttons[${idx}].label`, labelError);
    }
    
    const ccError = validators.cc(btn.cc);
    if (ccError) {
      errors.set(`buttons[${idx}].cc`, ccError);
    }
  });
  
  // Validate encoder
  if (config.encoder?.enabled) {
    const ccError = validators.cc(config.encoder.cc);
    if (ccError) {
      errors.set('encoder.cc', ccError);
    }
    
    if (config.encoder.min !== undefined && config.encoder.max !== undefined) {
      const rangeError = validators.range(config.encoder.min, config.encoder.max);
      if (rangeError) {
        errors.set('encoder.range', rangeError);
      }
    }
  }
  
  // Validate expression pedals
  if (config.expression?.exp1?.enabled) {
    const ccError = validators.cc(config.expression.exp1.cc);
    if (ccError) {
      errors.set('expression.exp1.cc', ccError);
    }
  }
  
  if (config.expression?.exp2?.enabled) {
    const ccError = validators.cc(config.expression.exp2.cc);
    if (ccError) {
      errors.set('expression.exp2.cc', ccError);
    }
  }
  
  // Check for duplicate CCs
  const duplicates = findDuplicateCC(config);
  duplicates.forEach((error, path) => {
    errors.set(path, error);
  });
  
  return {
    isValid: errors.size === 0,
    errors,
  };
}
```

Expected: Full validation function

**Step 3: Commit**

```bash
git add config-editor/src/lib/validation.ts
git commit -m "feat(validation): add form-level validation with duplicate CC detection"
```

---

### Task 2.3: Integrate Validation into Store

**Files:**
- Modify: `config-editor/src/lib/formStore.ts`

**Step 1: Import validation**

Add to imports at top:

```typescript
import { validateConfig } from './validation';
```

Expected: Import added

**Step 2: Add validate function**

Add after setDevice:

```typescript
export function validate() {
  const state = get(formState);
  const result = validateConfig(state.config);
  
  formState.update(s => ({
    ...s,
    validationErrors: result.errors,
  }));
  
  return result.isValid;
}
```

Expected: Validate function added

**Step 3: Add validation to updateField**

Modify updateField to add validation after update:

```typescript
export function updateField(path: string, value: any) {
  if (debounceTimer) {
    clearTimeout(debounceTimer);
  }
  
  formState.update(state => {
    const newConfig = structuredClone(state.config);
    setNestedValue(newConfig, path, value);
    
    return {
      ...state,
      config: newConfig,
      isDirty: true,
    };
  });
  
  // Validate after update
  validate();
  
  debounceTimer = setTimeout(() => {
    formState.update(state => pushHistory(state));
  }, DEBOUNCE_MS);
}
```

Expected: Validation runs on field update

**Step 4: Commit**

```bash
git add config-editor/src/lib/formStore.ts
git commit -m "feat(store): integrate validation on field updates"
```

---

## Phase 3: Base UI Components

### Task 3.1: Create Accordion Component

**Files:**
- Create: `config-editor/src/lib/components/Accordion.svelte`

**Step 1: Create accordion component**

Create file with:

```svelte
<script lang="ts">
  import { writable } from 'svelte/store';
  
  interface Props {
    title: string;
    defaultOpen?: boolean;
    disabled?: boolean;
    message?: string;
  }
  
  let { title, defaultOpen = true, disabled = false, message }: Props = $props();
  
  let isOpen = $state(defaultOpen);
  
  function toggle() {
    if (!disabled) {
      isOpen = !isOpen;
    }
  }
</script>

<div class="accordion">
  <button 
    class="accordion-header" 
    class:disabled 
    onclick={toggle}
    type="button"
  >
    <span class="triangle">{isOpen ? '▼' : '▶'}</span>
    <span class="title">{title}</span>
    {#if message}
      <span class="message">({message})</span>
    {/if}
  </button>
  
  {#if isOpen}
    <div class="accordion-content">
      {@render children()}
    </div>
  {/if}
</div>

<style>
  .accordion {
    margin-bottom: 1rem;
    border: 1px solid #ddd;
    border-radius: 4px;
  }
  
  .accordion-header {
    width: 100%;
    padding: 0.75rem 1rem;
    background: #f5f5f5;
    border: none;
    border-radius: 4px 4px 0 0;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 1rem;
    font-weight: 600;
    text-align: left;
  }
  
  .accordion-header:hover {
    background: #e5e5e5;
  }
  
  .accordion-header.disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
  
  .accordion-header.disabled:hover {
    background: #f5f5f5;
  }
  
  .triangle {
    font-size: 0.75rem;
    color: #666;
  }
  
  .title {
    flex: 1;
  }
  
  .message {
    color: #666;
    font-size: 0.875rem;
    font-weight: 400;
  }
  
  .accordion-content {
    padding: 1rem;
    background: white;
  }
</style>
```

Expected: Accordion component created

**Step 2: Commit**

```bash
git add config-editor/src/lib/components/Accordion.svelte
git commit -m "feat(ui): add accordion component"
```

---

### Task 3.2: Create ColorSelect Component

**Files:**
- Create: `config-editor/src/lib/components/ColorSelect.svelte`

**Step 1: Create color select component**

Create file with:

```svelte
<script lang="ts">
  import { BUTTON_COLORS, type ButtonColor } from '$lib/types';
  
  interface Props {
    value: ButtonColor;
    onchange: (color: ButtonColor) => void;
  }
  
  let { value, onchange }: Props = $props();
  
  let isOpen = $state(false);
  
  const colors: ButtonColor[] = [
    'red', 'green', 'blue', 'yellow',
    'cyan', 'magenta', 'orange', 'purple', 'white'
  ];
  
  function select(color: ButtonColor) {
    onchange(color);
    isOpen = false;
  }
  
  function toggle() {
    isOpen = !isOpen;
  }
  
  function handleClickOutside(event: MouseEvent) {
    const target = event.target as HTMLElement;
    if (!target.closest('.color-select')) {
      isOpen = false;
    }
  }
  
  $effect(() => {
    if (isOpen) {
      document.addEventListener('click', handleClickOutside);
      return () => document.removeEventListener('click', handleClickOutside);
    }
  });
</script>

<div class="color-select">
  <button 
    class="color-trigger" 
    onclick={toggle}
    type="button"
  >
    <span class="color-dot" style="background-color: {BUTTON_COLORS[value]}"></span>
    <span class="color-name">{value}</span>
    <span class="arrow">▼</span>
  </button>
  
  {#if isOpen}
    <div class="color-dropdown">
      {#each colors as color}
        <button
          class="color-option"
          class:selected={color === value}
          onclick={() => select(color)}
          type="button"
        >
          <span class="color-dot" style="background-color: {BUTTON_COLORS[color]}"></span>
          <span class="color-name">{color}</span>
          {#if color === value}
            <span class="checkmark">✓</span>
          {/if}
        </button>
      {/each}
    </div>
  {/if}
</div>

<style>
  .color-select {
    position: relative;
    display: inline-block;
  }
  
  .color-trigger {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.375rem 0.75rem;
    background: white;
    border: 1px solid #ccc;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.875rem;
  }
  
  .color-trigger:hover {
    border-color: #999;
  }
  
  .color-dot {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    border: 1px solid #666;
  }
  
  .color-name {
    text-transform: capitalize;
  }
  
  .arrow {
    font-size: 0.625rem;
    color: #666;
  }
  
  .color-dropdown {
    position: absolute;
    top: 100%;
    left: 0;
    margin-top: 2px;
    background: white;
    border: 1px solid #ccc;
    border-radius: 4px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.15);
    z-index: 1000;
    min-width: 140px;
  }
  
  .color-option {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    width: 100%;
    padding: 0.5rem 0.75rem;
    background: white;
    border: none;
    cursor: pointer;
    font-size: 0.875rem;
    text-align: left;
  }
  
  .color-option:hover {
    background: #f5f5f5;
  }
  
  .color-option.selected {
    background: #e8f4fd;
  }
  
  .checkmark {
    margin-left: auto;
    color: #0066cc;
    font-weight: bold;
  }
</style>
```

Expected: Color select component created

**Step 2: Commit**

```bash
git add config-editor/src/lib/components/ColorSelect.svelte
git commit -m "feat(ui): add color select dropdown component"
```

---

### Task 3.3: Create ConfigForm Shell

**Files:**
- Create: `config-editor/src/lib/components/ConfigForm.svelte`

**Step 1: Create form shell with toolbar**

Create file with:

```svelte
<script lang="ts">
  import { config, isDirty, canUndo, canRedo, undo, redo, validate } from '$lib/formStore';
  
  interface Props {
    onSave: () => void;
  }
  
  let { onSave }: Props = $props();
  
  let isValid = $state(true);
  let errorCount = $state(0);
  
  function handleUndo() {
    undo();
  }
  
  function handleRedo() {
    redo();
  }
  
  function handleSave() {
    isValid = validate();
    if (isValid) {
      onSave();
    }
  }
  
  function handleKeydown(e: KeyboardEvent) {
    if (e.metaKey || e.ctrlKey) {
      if (e.key === 'z' && !e.shiftKey) {
        e.preventDefault();
        if ($canUndo) handleUndo();
      } else if (e.key === 'z' && e.shiftKey) {
        e.preventDefault();
        if ($canRedo) handleRedo();
      } else if (e.key === 's') {
        e.preventDefault();
        if ($isDirty) handleSave();
      }
    }
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="config-form">
  <div class="toolbar">
    <button 
      class="btn" 
      disabled={!$canUndo} 
      onclick={handleUndo}
      title="Undo (⌘Z)"
    >
      ↶ Undo
    </button>
    
    <button 
      class="btn" 
      disabled={!$canRedo} 
      onclick={handleRedo}
      title="Redo (⌘⇧Z)"
    >
      ↷ Redo
    </button>
    
    <div class="spacer"></div>
    
    <button 
      class="btn btn-primary" 
      disabled={!$isDirty || !isValid} 
      onclick={handleSave}
      title="Save to Device (⌘S)"
    >
      {#if !isValid}
        Fix {errorCount} error{errorCount !== 1 ? 's' : ''} to save
      {:else}
        💾 Save to Device
      {/if}
    </button>
  </div>
  
  <div class="form-content">
    {@render children()}
  </div>
</div>

<style>
  .config-form {
    display: flex;
    flex-direction: column;
    height: 100%;
  }
  
  .toolbar {
    display: flex;
    gap: 0.5rem;
    padding: 0.75rem;
    background: #f8f8f8;
    border-bottom: 1px solid #ddd;
  }
  
  .btn {
    padding: 0.5rem 1rem;
    background: white;
    border: 1px solid #ccc;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.875rem;
  }
  
  .btn:hover:not(:disabled) {
    background: #f5f5f5;
    border-color: #999;
  }
  
  .btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  
  .btn-primary {
    background: #0066cc;
    color: white;
    border-color: #0066cc;
  }
  
  .btn-primary:hover:not(:disabled) {
    background: #0052a3;
    border-color: #0052a3;
  }
  
  .spacer {
    flex: 1;
  }
  
  .form-content {
    flex: 1;
    overflow-y: auto;
    padding: 1rem;
  }
</style>
```

Expected: Form shell with toolbar created

**Step 2: Commit**

```bash
git add config-editor/src/lib/components/ConfigForm.svelte
git commit -m "feat(ui): add config form shell with toolbar and keyboard shortcuts"
```

---

## Phase 4: Button Section

### Task 4.1: Create ButtonRow Component

**Files:**
- Create: `config-editor/src/lib/components/ButtonRow.svelte`

**Step 1: Create button row component**

Create file with:

```svelte
<script lang="ts">
  import ColorSelect from './ColorSelect.svelte';
  import type { ButtonConfig, ButtonColor, ButtonMode, OffMode } from '$lib/types';
  import { validationErrors } from '$lib/formStore';
  
  interface Props {
    button: ButtonConfig;
    index: number;
    disabled?: boolean;
    onUpdate: (field: string, value: any) => void;
  }
  
  let { button, index, disabled = false, onUpdate }: Props = $props();
  
  const basePath = `buttons[${index}]`;
  
  function handleLabelChange(e: Event) {
    const target = e.target as HTMLInputElement;
    onUpdate('label', target.value);
  }
  
  function handleCCChange(e: Event) {
    const target = e.target as HTMLInputElement;
    onUpdate('cc', parseInt(target.value));
  }
  
  function handleColorChange(color: ButtonColor) {
    onUpdate('color', color);
  }
  
  function handleModeChange(e: Event) {
    const target = e.target as HTMLSelectElement;
    onUpdate('mode', target.value as ButtonMode);
  }
  
  function handleOffModeChange(e: Event) {
    const target = e.target as HTMLSelectElement;
    onUpdate('off_mode', target.value as OffMode);
  }
  
  $: labelError = $validationErrors.get(`${basePath}.label`);
  $: ccError = $validationErrors.get(`${basePath}.cc`);
</script>

<div class="button-row" class:disabled>
  <span class="button-num">Button {index + 1}:</span>
  
  <div class="field">
    <input 
      type="text" 
      class="input-label"
      class:error={!!labelError}
      value={button.label}
      onblur={handleLabelChange}
      disabled={disabled}
      maxlength="6"
      placeholder="Label"
    />
    {#if labelError}
      <span class="error-text">{labelError}</span>
    {/if}
  </div>
  
  <div class="field">
    <label class="field-label">CC:</label>
    <input 
      type="number" 
      class="input-cc"
      class:error={!!ccError}
      value={button.cc}
      onblur={handleCCChange}
      disabled={disabled}
      min="0"
      max="127"
    />
    {#if ccError}
      <span class="error-text">{ccError}</span>
    {/if}
  </div>
  
  <div class="field">
    <label class="field-label">Color:</label>
    <ColorSelect 
      value={button.color} 
      onchange={handleColorChange}
    />
  </div>
  
  <div class="field">
    <label class="field-label">Mode:</label>
    <select 
      class="select"
      value={button.mode || 'toggle'}
      onchange={handleModeChange}
      disabled={disabled}
    >
      <option value="toggle">Toggle</option>
      <option value="momentary">Momentary</option>
    </select>
  </div>
  
  <div class="field">
    <label class="field-label">Off:</label>
    <select 
      class="select"
      value={button.off_mode || 'dim'}
      onchange={handleOffModeChange}
      disabled={disabled}
    >
      <option value="dim">Dim</option>
      <option value="off">Off</option>
    </select>
  </div>
  
  {#if disabled}
    <div class="disabled-overlay">
      Not available on Mini6
    </div>
  {/if}
</div>

<style>
  .button-row {
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    padding: 0.5rem;
    border: 1px solid #e5e5e5;
    border-radius: 4px;
    margin-bottom: 0.5rem;
    position: relative;
  }
  
  .button-row.disabled {
    opacity: 0.6;
    background: #f9f9f9;
  }
  
  .button-num {
    font-weight: 500;
    color: #666;
    min-width: 80px;
    padding-top: 0.4rem;
  }
  
  .field {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    flex-direction: column;
    position: relative;
  }
  
  .field-label {
    font-size: 0.75rem;
    color: #666;
    align-self: flex-start;
  }
  
  .input-label {
    width: 80px;
    padding: 0.375rem 0.5rem;
    border: 1px solid #ccc;
    border-radius: 4px;
    font-size: 0.875rem;
  }
  
  .input-cc {
    width: 60px;
    padding: 0.375rem 0.5rem;
    border: 1px solid #ccc;
    border-radius: 4px;
    font-size: 0.875rem;
  }
  
  .select {
    padding: 0.375rem 0.5rem;
    border: 1px solid #ccc;
    border-radius: 4px;
    font-size: 0.875rem;
    background: white;
  }
  
  input.error,
  select.error {
    border-color: #dc3545;
  }
  
  .error-text {
    position: absolute;
    top: 100%;
    left: 0;
    font-size: 0.75rem;
    color: #dc3545;
    white-space: nowrap;
    margin-top: 2px;
  }
  
  .disabled-overlay {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(255, 255, 255, 0.8);
    color: #666;
    font-size: 0.875rem;
    font-weight: 500;
    pointer-events: none;
  }
</style>
```

Expected: Button row component created

**Step 2: Commit**

```bash
git add config-editor/src/lib/components/ButtonRow.svelte
git commit -m "feat(ui): add button row component with validation"
```

---

### Task 4.2: Create ButtonsSection Component

**Files:**
- Create: `config-editor/src/lib/components/ButtonsSection.svelte`

**Step 1: Create buttons section**

Create file with:

```svelte
<script lang="ts">
  import Accordion from './Accordion.svelte';
  import ButtonRow from './ButtonRow.svelte';
  import { config, updateField } from '$lib/formStore';
  
  $: deviceType = $config.device;
  $: buttons = $config.buttons;
  $: visibleCount = buttons.length;
  
  function handleButtonUpdate(index: number, field: string, value: any) {
    updateField(`buttons[${index}].${field}`, value);
  }
</script>

<Accordion title="Buttons ({visibleCount} of {visibleCount})">
  <div class="buttons-list">
    {#each buttons as button, index}
      {@const isDisabled = deviceType === 'mini6' && index >= 6}
      <ButtonRow 
        {button}
        {index}
        disabled={isDisabled}
        onUpdate={(field, value) => handleButtonUpdate(index, field, value)}
      />
    {/each}
  </div>
</Accordion>

<style>
  .buttons-list {
    display: flex;
    flex-direction: column;
  }
</style>
```

Expected: Buttons section created

**Step 2: Commit**

```bash
git add config-editor/src/lib/components/ButtonsSection.svelte
git commit -m "feat(ui): add buttons section with device-specific visibility"
```

---

## Phase 5: Encoder & Expression Sections

### Task 5.1: Create DeviceSection Component

**Files:**
- Create: `config-editor/src/lib/components/DeviceSection.svelte`

**Step 1: Create device section**

Create file with:

```svelte
<script lang="ts">
  import Accordion from './Accordion.svelte';
  import { config, setDevice } from '$lib/formStore';
  import type { DeviceType } from '$lib/types';
  
  function handleDeviceChange(e: Event) {
    const target = e.target as HTMLSelectElement;
    setDevice(target.value as DeviceType);
  }
</script>

<Accordion title="Device Settings">
  <div class="device-section">
    <label for="device-type">Device Type:</label>
    <select 
      id="device-type"
      class="select"
      value={$config.device}
      onchange={handleDeviceChange}
    >
      <option value="std10">STD10 (10 buttons)</option>
      <option value="mini6">Mini6 (6 buttons)</option>
    </select>
    
    <p class="help-text">
      {#if $config.device === 'mini6'}
        Mini6 supports 6 buttons only. Encoder and expression pedals are not available.
      {:else}
        STD10 supports 10 buttons, encoder, and expression pedals.
      {/if}
    </p>
  </div>
</Accordion>

<style>
  .device-section {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  
  label {
    font-weight: 500;
  }
  
  .select {
    padding: 0.5rem;
    border: 1px solid #ccc;
    border-radius: 4px;
    font-size: 0.875rem;
    background: white;
    max-width: 250px;
  }
  
  .help-text {
    font-size: 0.875rem;
    color: #666;
    margin: 0;
  }
</style>
```

Expected: Device section created

**Step 2: Commit**

```bash
git add config-editor/src/lib/components/DeviceSection.svelte
git commit -m "feat(ui): add device selection section"
```

---

### Task 5.2: Create EncoderSection Component

**Files:**
- Create: `config-editor/src/lib/components/EncoderSection.svelte`

**Step 1: Create encoder section**

Create file with:

```svelte
<script lang="ts">
  import Accordion from './Accordion.svelte';
  import { config, updateField } from '$lib/formStore';
  import { validationErrors } from '$lib/formStore';
  
  $: deviceType = $config.device;
  $: encoder = $config.encoder;
  $: isDisabled = deviceType === 'mini6';
  $: message = isDisabled ? 'Disabled on Mini6' : undefined;
  
  function handleField(path: string, e: Event) {
    const target = e.target as HTMLInputElement | HTMLSelectElement;
    const value = target.type === 'checkbox' 
      ? (target as HTMLInputElement).checked
      : target.type === 'number'
      ? parseInt(target.value)
      : target.value;
    
    updateField(`encoder.${path}`, value);
  }
  
  $: ccError = $validationErrors.get('encoder.cc');
  $: pushCCError = $validationErrors.get('encoder.push.cc');
</script>

<Accordion 
  title="Encoder" 
  defaultOpen={!isDisabled}
  disabled={isDisabled}
  {message}
>
  {#if encoder}
    <div class="encoder-section">
      <div class="field-row">
        <label>
          <input 
            type="checkbox" 
            checked={encoder.enabled || false}
            onchange={(e) => handleField('enabled', e)}
            disabled={isDisabled}
          />
          Enabled
        </label>
      </div>
      
      {#if encoder.enabled}
        <div class="field-row">
          <label>CC:</label>
          <input 
            type="number" 
            class:error={!!ccError}
            value={encoder.cc}
            onblur={(e) => handleField('cc', e)}
            min="0"
            max="127"
            disabled={isDisabled}
          />
          {#if ccError}
            <span class="error-text">{ccError}</span>
          {/if}
        </div>
        
        <div class="field-row">
          <label>Label:</label>
          <input 
            type="text" 
            value={encoder.label}
            onblur={(e) => handleField('label', e)}
            maxlength="6"
            disabled={isDisabled}
          />
        </div>
        
        <div class="field-row">
          <label>Min:</label>
          <input 
            type="number" 
            value={encoder.min ?? 0}
            onblur={(e) => handleField('min', e)}
            min="0"
            max="127"
            disabled={isDisabled}
          />
        </div>
        
        <div class="field-row">
          <label>Max:</label>
          <input 
            type="number" 
            value={encoder.max ?? 127}
            onblur={(e) => handleField('max', e)}
            min="0"
            max="127"
            disabled={isDisabled}
          />
        </div>
        
        <div class="field-row">
          <label>Initial:</label>
          <input 
            type="number" 
            value={encoder.initial ?? 64}
            onblur={(e) => handleField('initial', e)}
            min="0"
            max="127"
            disabled={isDisabled}
          />
        </div>
        
        <h4>Encoder Push Button</h4>
        
        <div class="field-row">
          <label>
            <input 
              type="checkbox" 
              checked={encoder.push?.enabled || false}
              onchange={(e) => handleField('push.enabled', e)}
              disabled={isDisabled}
            />
            Enabled
          </label>
        </div>
        
        {#if encoder.push?.enabled}
          <div class="field-row">
            <label>CC:</label>
            <input 
              type="number" 
              class:error={!!pushCCError}
              value={encoder.push.cc}
              onblur={(e) => handleField('push.cc', e)}
              min="0"
              max="127"
              disabled={isDisabled}
            />
            {#if pushCCError}
              <span class="error-text">{pushCCError}</span>
            {/if}
          </div>
          
          <div class="field-row">
            <label>Label:</label>
            <input 
              type="text" 
              value={encoder.push.label}
              onblur={(e) => handleField('push.label', e)}
              maxlength="6"
              disabled={isDisabled}
            />
          </div>
          
          <div class="field-row">
            <label>Mode:</label>
            <select 
              value={encoder.push.mode || 'momentary'}
              onchange={(e) => handleField('push.mode', e)}
              disabled={isDisabled}
            >
              <option value="toggle">Toggle</option>
              <option value="momentary">Momentary</option>
            </select>
          </div>
        {/if}
      {/if}
    </div>
  {/if}
</Accordion>

<style>
  .encoder-section {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }
  
  .field-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    position: relative;
  }
  
  .field-row label {
    min-width: 80px;
    font-size: 0.875rem;
  }
  
  .field-row input[type="text"],
  .field-row input[type="number"],
  .field-row select {
    padding: 0.375rem 0.5rem;
    border: 1px solid #ccc;
    border-radius: 4px;
    font-size: 0.875rem;
  }
  
  .field-row input[type="checkbox"] {
    margin-right: 0.25rem;
  }
  
  input.error {
    border-color: #dc3545;
  }
  
  .error-text {
    position: absolute;
    left: 100px;
    top: 100%;
    font-size: 0.75rem;
    color: #dc3545;
    white-space: nowrap;
  }
  
  h4 {
    margin: 0.5rem 0 0 0;
    font-size: 0.875rem;
    color: #666;
  }
</style>
```

Expected: Encoder section created

**Step 2: Commit**

```bash
git add config-editor/src/lib/components/EncoderSection.svelte
git commit -m "feat(ui): add encoder section with push button support"
```

---

### Task 5.3: Create ExpressionSection Component

**Files:**
- Create: `config-editor/src/lib/components/ExpressionSection.svelte`

**Step 1: Create expression section**

Create file with:

```svelte
<script lang="ts">
  import Accordion from './Accordion.svelte';
  import { config, updateField } from '$lib/formStore';
  import { validationErrors } from '$lib/formStore';
  
  $: expression = $config.expression;
  
  function handleField(pedalNum: 'exp1' | 'exp2', path: string, e: Event) {
    const target = e.target as HTMLInputElement | HTMLSelectElement;
    const value = target.type === 'checkbox' 
      ? (target as HTMLInputElement).checked
      : target.type === 'number'
      ? parseInt(target.value)
      : target.value;
    
    updateField(`expression.${pedalNum}.${path}`, value);
  }
  
  $: exp1CCError = $validationErrors.get('expression.exp1.cc');
  $: exp2CCError = $validationErrors.get('expression.exp2.cc');
</script>

<Accordion title="Expression Pedals">
  {#if expression}
    <div class="expression-section">
      <h4>Expression 1</h4>
      
      <div class="field-row">
        <label>
          <input 
            type="checkbox" 
            checked={expression.exp1?.enabled || false}
            onchange={(e) => handleField('exp1', 'enabled', e)}
          />
          Enabled
        </label>
      </div>
      
      {#if expression.exp1?.enabled}
        <div class="field-row">
          <label>CC:</label>
          <input 
            type="number" 
            class:error={!!exp1CCError}
            value={expression.exp1.cc}
            onblur={(e) => handleField('exp1', 'cc', e)}
            min="0"
            max="127"
          />
          {#if exp1CCError}
            <span class="error-text">{exp1CCError}</span>
          {/if}
        </div>
        
        <div class="field-row">
          <label>Label:</label>
          <input 
            type="text" 
            value={expression.exp1.label}
            onblur={(e) => handleField('exp1', 'label', e)}
            maxlength="6"
          />
        </div>
        
        <div class="field-row">
          <label>Min:</label>
          <input 
            type="number" 
            value={expression.exp1.min ?? 0}
            onblur={(e) => handleField('exp1', 'min', e)}
            min="0"
            max="127"
          />
        </div>
        
        <div class="field-row">
          <label>Max:</label>
          <input 
            type="number" 
            value={expression.exp1.max ?? 127}
            onblur={(e) => handleField('exp1', 'max', e)}
            min="0"
            max="127"
          />
        </div>
        
        <div class="field-row">
          <label>Polarity:</label>
          <select 
            value={expression.exp1.polarity || 'normal'}
            onchange={(e) => handleField('exp1', 'polarity', e)}
          >
            <option value="normal">Normal</option>
            <option value="inverted">Inverted</option>
          </select>
        </div>
        
        <div class="field-row">
          <label>Threshold:</label>
          <input 
            type="number" 
            value={expression.exp1.threshold ?? 2}
            onblur={(e) => handleField('exp1', 'threshold', e)}
            min="0"
            max="10"
          />
        </div>
      {/if}
      
      <h4>Expression 2</h4>
      
      <div class="field-row">
        <label>
          <input 
            type="checkbox" 
            checked={expression.exp2?.enabled || false}
            onchange={(e) => handleField('exp2', 'enabled', e)}
          />
          Enabled
        </label>
      </div>
      
      {#if expression.exp2?.enabled}
        <div class="field-row">
          <label>CC:</label>
          <input 
            type="number" 
            class:error={!!exp2CCError}
            value={expression.exp2.cc}
            onblur={(e) => handleField('exp2', 'cc', e)}
            min="0"
            max="127"
          />
          {#if exp2CCError}
            <span class="error-text">{exp2CCError}</span>
          {/if}
        </div>
        
        <div class="field-row">
          <label>Label:</label>
          <input 
            type="text" 
            value={expression.exp2.label}
            onblur={(e) => handleField('exp2', 'label', e)}
            maxlength="6"
          />
        </div>
        
        <div class="field-row">
          <label>Min:</label>
          <input 
            type="number" 
            value={expression.exp2.min ?? 0}
            onblur={(e) => handleField('exp2', 'min', e)}
            min="0"
            max="127"
          />
        </div>
        
        <div class="field-row">
          <label>Max:</label>
          <input 
            type="number" 
            value={expression.exp2.max ?? 127}
            onblur={(e) => handleField('exp2', 'max', e)}
            min="0"
            max="127"
          />
        </div>
        
        <div class="field-row">
          <label>Polarity:</label>
          <select 
            value={expression.exp2.polarity || 'normal'}
            onchange={(e) => handleField('exp2', 'polarity', e)}
          >
            <option value="normal">Normal</option>
            <option value="inverted">Inverted</option>
          </select>
        </div>
        
        <div class="field-row">
          <label>Threshold:</label>
          <input 
            type="number" 
            value={expression.exp2.threshold ?? 2}
            onblur={(e) => handleField('exp2', 'threshold', e)}
            min="0"
            max="10"
          />
        </div>
      {/if}
    </div>
  {/if}
</Accordion>

<style>
  .expression-section {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }
  
  .field-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    position: relative;
  }
  
  .field-row label {
    min-width: 80px;
    font-size: 0.875rem;
  }
  
  .field-row input[type="text"],
  .field-row input[type="number"],
  .field-row select {
    padding: 0.375rem 0.5rem;
    border: 1px solid #ccc;
    border-radius: 4px;
    font-size: 0.875rem;
  }
  
  .field-row input[type="checkbox"] {
    margin-right: 0.25rem;
  }
  
  input.error {
    border-color: #dc3545;
  }
  
  .error-text {
    position: absolute;
    left: 100px;
    top: 100%;
    font-size: 0.75rem;
    color: #dc3545;
    white-space: nowrap;
  }
  
  h4 {
    margin: 1rem 0 0 0;
    font-size: 1rem;
    color: #333;
  }
  
  h4:first-child {
    margin-top: 0;
  }
</style>
```

Expected: Expression section created

**Step 2: Commit**

```bash
git add config-editor/src/lib/components/ExpressionSection.svelte
git commit -m "feat(ui): add expression pedals section"
```

---

## Phase 6: Display Section & Polish

### Task 6.1: Create DisplaySection Component

**Files:**
- Create: `config-editor/src/lib/components/DisplaySection.svelte`

**Step 1: Create display section**

Create file with:

```svelte
<script lang="ts">
  import Accordion from './Accordion.svelte';
  import { config, updateField } from '$lib/formStore';
  
  $: display = $config.display;
  
  function handleField(path: string, e: Event) {
    const target = e.target as HTMLSelectElement;
    updateField(`display.${path}`, target.value);
  }
</script>

<Accordion title="Display Settings">
  {#if display}
    <div class="display-section">
      <div class="field-row">
        <label>Button text size:</label>
        <select 
          value={display.button_text_size}
          onchange={(e) => handleField('button_text_size', e)}
        >
          <option value="small">Small</option>
          <option value="medium">Medium</option>
          <option value="large">Large</option>
        </select>
      </div>
      
      <div class="field-row">
        <label>Status text size:</label>
        <select 
          value={display.status_text_size}
          onchange={(e) => handleField('status_text_size', e)}
        >
          <option value="small">Small</option>
          <option value="medium">Medium</option>
          <option value="large">Large</option>
        </select>
      </div>
      
      <div class="field-row">
        <label>Expression text size:</label>
        <select 
          value={display.expression_text_size}
          onchange={(e) => handleField('expression_text_size', e)}
        >
          <option value="small">Small</option>
          <option value="medium">Medium</option>
          <option value="large">Large</option>
        </select>
      </div>
    </div>
  {/if}
</Accordion>

<style>
  .display-section {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }
  
  .field-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  
  .field-row label {
    min-width: 160px;
    font-size: 0.875rem;
  }
  
  .field-row select {
    padding: 0.375rem 0.5rem;
    border: 1px solid #ccc;
    border-radius: 4px;
    font-size: 0.875rem;
    background: white;
    min-width: 120px;
  }
</style>
```

Expected: Display section created

**Step 2: Commit**

```bash
git add config-editor/src/lib/components/DisplaySection.svelte
git commit -m "feat(ui): add display settings section"
```

---

## Phase 7: Integration & Testing

### Task 7.1: Integrate ConfigForm into Main Page

**Files:**
- Modify: `config-editor/src/routes/+page.svelte`

**Step 1: Import new components**

Replace JsonEditor import with ConfigForm:

```typescript
import ConfigForm from '$lib/components/ConfigForm.svelte';
import DeviceSection from '$lib/components/DeviceSection.svelte';
import ButtonsSection from '$lib/components/ButtonsSection.svelte';
import EncoderSection from '$lib/components/EncoderSection.svelte';
import ExpressionSection from '$lib/components/ExpressionSection.svelte';
import DisplaySection from '$lib/components/DisplaySection.svelte';
import { loadConfig, validate } from '$lib/formStore';
```

Expected: Imports updated

**Step 2: Update selectDevice to use loadConfig**

Find the selectDevice function and update it to use formStore:

```typescript
async function selectDevice(device: DetectedDevice) {
  $selectedDevice = device;
  $isLoading = true;
  
  try {
    const configRaw = await readConfigRaw(device.config_path);
    const configObj = JSON.parse(configRaw);
    
    // Load into form store
    loadConfig(configObj);
    
    $currentConfigRaw = configRaw;
    $hasUnsavedChanges = false;
    $validationErrors = [];
    $statusMessage = 'Config loaded successfully';
  } catch (e: any) {
    $statusMessage = `Error loading config: ${e.message || e}`;
    await message($statusMessage, { title: 'Error', kind: 'error' });
  } finally {
    $isLoading = false;
  }
}
```

Expected: selectDevice updated

**Step 3: Replace JsonEditor with ConfigForm in template**

Find the JsonEditor component in the template and replace with:

```svelte
{#if $selectedDevice && !$isLoading}
  <ConfigForm onSave={saveToDevice}>
    <DeviceSection />
    <ButtonsSection />
    <EncoderSection />
    <ExpressionSection />
    <DisplaySection />
  </ConfigForm>
{:else if $isLoading}
  <div class="loading">Loading config...</div>
{:else}
  <div class="no-device">
    <p>No device selected</p>
    <p>Connect a MIDI Captain device and select it above</p>
  </div>
{/if}
```

Expected: Template updated

**Step 4: Update saveToDevice to use formStore**

Replace saveToDevice function:

```typescript
async function saveToDevice() {
  if (!$selectedDevice) return;
  
  const isValid = validate();
  if (!isValid) {
    await message('Please fix validation errors before saving', { 
      title: 'Validation Error', 
      kind: 'error' 
    });
    return;
  }
  
  $isLoading = true;
  
  try {
    const configObj = get(config);
    const configJson = JSON.stringify(configObj, null, 2);
    
    await writeConfigRaw($selectedDevice.config_path, configJson);
    
    $currentConfigRaw = configJson;
    $hasUnsavedChanges = false;
    $statusMessage = 'Config saved successfully';
    
    await message('Config saved to device successfully!', { 
      title: 'Success', 
      kind: 'info' 
    });
  } catch (e: any) {
    $statusMessage = `Error saving config: ${e.message || e}`;
    await message($statusMessage, { title: 'Error', kind: 'error' });
  } finally {
    $isLoading = false;
  }
}
```

Expected: Save function updated

**Step 5: Add import for get from svelte/store**

Add to imports:

```typescript
import { get } from 'svelte/store';
```

Expected: Import added

**Step 6: Commit**

```bash
git add config-editor/src/routes/+page.svelte
git commit -m "feat: integrate config form into main page"
```

---

### Task 7.2: Test Device Switching Flow

**Step 1: Start dev server**

Run:
```bash
npm run tauri dev
```

Expected: App opens successfully

**Step 2: Manual testing checklist**

Test all these scenarios:

1. Load config from device
2. Edit button label → verify immediate UI update
3. Press ⌘Z → verify undo works
4. Press ⌘⇧Z → verify redo works
5. Switch device STD10 → Mini6 → verify buttons 7-10 grayed out
6. Switch back Mini6 → STD10 → verify buttons 7-10 restored
7. Enter invalid CC (e.g., 200) → verify error appears
8. Create duplicate CC → verify both fields show error
9. Press ⌘S with errors → verify save blocked
10. Fix errors, press ⌘S → verify save succeeds

Expected: All scenarios work correctly

**Step 3: Document any issues**

If any issues found, create GitHub issues for them.

Expected: Issues logged

**Step 4: Commit any fixes**

```bash
git add .
git commit -m "fix: address testing issues"
```

---

### Task 7.3: Final Polish

**Step 1: Add global styles**

Create `config-editor/src/app.css` if it doesn't exist:

```css
* {
  box-sizing: border-box;
}

body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 
    'Helvetica Neue', Arial, sans-serif;
  font-size: 14px;
  line-height: 1.5;
  color: #333;
  background: #fff;
}

h1, h2, h3, h4, h5, h6 {
  margin: 0;
  font-weight: 600;
}

button {
  font-family: inherit;
}

input, select, textarea {
  font-family: inherit;
  font-size: inherit;
}
```

Expected: Global styles added

**Step 2: Import in main.ts**

Add to top of `config-editor/src/main.ts`:

```typescript
import './app.css';
```

Expected: Styles imported

**Step 3: Commit**

```bash
git add config-editor/src/app.css config-editor/src/main.ts
git commit -m "style: add global styles for consistent typography"
```

---

### Task 7.4: Create PR

**Step 1: Push branch**

Run:
```bash
git push -u origin config-form-editor
```

Expected: Branch pushed to GitHub

**Step 2: Create pull request**

Go to GitHub and create PR with description:

```markdown
## Config Form Editor

Replaces JSON text editor with visual form UI featuring:

- ✅ Form-first UX with proper controls (dropdowns, toggles, text fields)
- ✅ Undo/redo support (⌘Z/⌘⇧Z)
- ✅ Real-time validation with inline errors
- ✅ Device-specific field handling (Mini6 vs STD10)
- ✅ Data preservation when switching device types
- ✅ Keyboard shortcuts (⌘S to save)

### Components Added
- DeviceSection - Device type selection
- ButtonsSection - Button configuration with 6-10 buttons
- EncoderSection - Encoder + push button config
- ExpressionSection - Expression pedal configuration
- DisplaySection - Text size settings

### State Management
- Centralized formStore with history tracking
- Field-level and form-level validation
- Debounced history for efficient undo/redo

Closes #5
```

Expected: PR created

---

## Complete!

All phases implemented. The config form editor is now ready for review and testing.

**Next steps:**
1. Review PR
2. Test on actual hardware
3. Gather user feedback
4. Iterate on UX improvements
