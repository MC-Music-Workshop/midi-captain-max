<script lang="ts">
  import ColorSelect from './ColorSelect.svelte';
  import type { ButtonConfig, ButtonColor, ButtonMode, OffMode, MessageType } from '$lib/types';
  import { validationErrors, syncButtonStates } from '$lib/formStore';

  interface Props {
    button: ButtonConfig;
    index: number;
    displayName?: string;
    disabled?: boolean;
    globalChannel?: number;
    onUpdate: (field: string, value: any) => void;
  }

  let { button, index, displayName, disabled = false, globalChannel = 0, onUpdate }: Props = $props();

  let basePath = $derived(`buttons[${index}]`);
  let idPrefix = $derived(`btn-${index}`);
  const fieldId = (field: string) => `${idPrefix}-${field}`;
  const stateFieldId = (si: number, field: string) => `${idPrefix}-state-${si}-${field}`;

  let msgType = $derived((button.type ?? 'cc') as MessageType);
  let isCC = $derived(msgType === 'cc');
  let isNote = $derived(msgType === 'note');
  let isPC = $derived(msgType === 'pc');
  let isPCIncDec = $derived(msgType === 'pc_inc' || msgType === 'pc_dec');
  let showMode = $derived(isCC || isNote);

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

  function handleChannelChange(e: Event) {
    const target = e.target as HTMLInputElement;
    if (target.value === '') {
      onUpdate('channel', undefined);
    } else {
      const value = parseInt(target.value);
      // Convert from 1-16 display to 0-15 storage
      onUpdate('channel', value - 1);
    }
  }

  function handleCCOnChange(e: Event) {
    const target = e.target as HTMLInputElement;
    const value = target.value === '' ? undefined : parseInt(target.value);
    onUpdate('cc_on', value);
  }

  function handleCCOffChange(e: Event) {
    const target = e.target as HTMLInputElement;
    const value = target.value === '' ? undefined : parseInt(target.value);
    onUpdate('cc_off', value);
  }

  function handleTypeChange(e: Event) {
    const target = e.target as HTMLSelectElement;
    onUpdate('type', target.value as MessageType);
  }

  function handleNoteChange(e: Event) {
    const target = e.target as HTMLInputElement;
    onUpdate('note', parseInt(target.value));
  }

  function handleVelocityOnChange(e: Event) {
    const target = e.target as HTMLInputElement;
    const value = target.value === '' ? undefined : parseInt(target.value);
    onUpdate('velocity_on', value);
  }

  function handleVelocityOffChange(e: Event) {
    const target = e.target as HTMLInputElement;
    const value = target.value === '' ? undefined : parseInt(target.value);
    onUpdate('velocity_off', value);
  }

  function handleProgramChange(e: Event) {
    const target = e.target as HTMLInputElement;
    onUpdate('program', parseInt(target.value));
  }

  function handlePCStepChange(e: Event) {
    const target = e.target as HTMLInputElement;
    onUpdate('pc_step', parseInt(target.value));
  }

  function handleFlashMsChange(e: Event) {
    const target = e.target as HTMLInputElement;
    const value = target.value === '' ? undefined : parseInt(target.value);
    onUpdate('flash_ms', value);
  }

  let flashMsError = $derived($validationErrors.get(`${basePath}.flash_ms`));

  let hasKeytimes = $derived((button.keytimes ?? 1) > 1);
  let keytimesError = $derived($validationErrors.get(`${basePath}.keytimes`));

  function handleKeytimesChange(e: Event) {
    const target = e.target as HTMLInputElement;
    const value = target.value === '' ? 1 : Math.min(99, Math.max(1, parseInt(target.value) || 1));
    syncButtonStates(index, value);
  }

  function handleStateFieldChange(si: number, field: string, e: Event) {
    const target = e.target as HTMLInputElement;
    const value = target.value === '' ? undefined : parseInt(target.value);
    onUpdate(`states[${si}].${field}`, value);
  }

  function handleStateColorChange(si: number, color: ButtonColor) {
    onUpdate(`states[${si}].color`, color);
  }

  function handleStateLabelChange(si: number, e: Event) {
    const target = e.target as HTMLInputElement;
    onUpdate(`states[${si}].label`, target.value === '' ? undefined : target.value);
  }

  function stateError(si: number, field: string): string | undefined {
    return $validationErrors.get(`${basePath}.states[${si}].${field}`);
  }

  let labelError = $derived($validationErrors.get(`${basePath}.label`));
  let ccError = $derived($validationErrors.get(`${basePath}.cc`));
  let channelError = $derived($validationErrors.get(`${basePath}.channel`));
  let ccOnError = $derived($validationErrors.get(`${basePath}.cc_on`));
  let ccOffError = $derived($validationErrors.get(`${basePath}.cc_off`));
  let noteError = $derived($validationErrors.get(`${basePath}.note`));
  let velocityOnError = $derived($validationErrors.get(`${basePath}.velocity_on`));
  let velocityOffError = $derived($validationErrors.get(`${basePath}.velocity_off`));
  let programError = $derived($validationErrors.get(`${basePath}.program`));
  let pcStepError = $derived($validationErrors.get(`${basePath}.pc_step`));

  // Display effective channel as 1-16 (stored internally as 0-15)
  let effectiveChannel = $derived(
    button.channel !== undefined ? button.channel + 1 : globalChannel + 1
  );

  // Display button channel as 1-16 if set (stored as 0-15)
  let displayChannel = $derived(
    button.channel !== undefined ? button.channel + 1 : undefined
  );

</script>

<div class="button-row" class:disabled>
  <span class="button-num">{displayName ?? `Button ${index + 1}`}:</span>

  <div class="field">
    <label class="visually-hidden" for={fieldId('label')}>Label</label>
    <input
      id={fieldId('label')}
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
    <label class="field-label" for={fieldId('type')}>Type:</label>
    <select
      id={fieldId('type')}
      class="select"
      value={button.type ?? 'cc'}
      onchange={handleTypeChange}
      disabled={disabled}
    >
      <option value="cc">CC</option>
      <option value="note">Note</option>
      <option value="pc">PC Fixed</option>
      <option value="pc_inc">PC+</option>
      <option value="pc_dec">PC-</option>
    </select>
  </div>

  <div class="field">
    <label class="field-label" for={fieldId('channel')}>Channel:</label>
    <input
      id={fieldId('channel')}
      type="number"
      class="input-channel"
      class:error={!!channelError}
      value={displayChannel !== undefined ? displayChannel : ''}
      onblur={handleChannelChange}
      disabled={disabled}
      min="1"
      max="16"
      placeholder={effectiveChannel.toString()}
      title={button.channel !== undefined ? `MIDI Ch ${effectiveChannel}` : `Using global: ${effectiveChannel}`}
    />
    {#if channelError}
      <span class="error-text">{channelError}</span>
    {/if}
  </div>

  {#if isCC}
    <div class="field">
      <label class="field-label" for={fieldId('cc')}>CC:</label>
      <input id={fieldId('cc')} type="number" class="input-cc" class:error={!!ccError}
        value={button.cc ?? ''} onblur={handleCCChange} disabled={disabled}
        min="0" max="127" />
      {#if ccError}<span class="error-text">{ccError}</span>{/if}
    </div>
    <div class="field">
      <label class="field-label" for={fieldId('cc-on')}>ON Value:</label>
      <input id={fieldId('cc-on')} type="number" class="input-cc-value" class:error={!!ccOnError}
        value={button.cc_on !== undefined ? button.cc_on : ''} onblur={handleCCOnChange}
        disabled={disabled} min="0" max="127" placeholder="127" />
      {#if ccOnError}<span class="error-text">{ccOnError}</span>{/if}
    </div>
    <div class="field">
      <label class="field-label" for={fieldId('cc-off')}>OFF Value:</label>
      <input id={fieldId('cc-off')} type="number" class="input-cc-value" class:error={!!ccOffError}
        value={button.cc_off !== undefined ? button.cc_off : ''} onblur={handleCCOffChange}
        disabled={disabled} min="0" max="127" placeholder="0" />
      {#if ccOffError}<span class="error-text">{ccOffError}</span>{/if}
    </div>
  {:else if isNote}
    <div class="field">
      <label class="field-label" for={fieldId('note')}>Note:</label>
      <input id={fieldId('note')} type="number" class="input-cc" class:error={!!noteError}
        value={button.note ?? 60} onblur={handleNoteChange} disabled={disabled}
        min="0" max="127" />
      {#if noteError}<span class="error-text">{noteError}</span>{/if}
    </div>
    <div class="field">
      <label class="field-label" for={fieldId('vel-on')}>Vel ON:</label>
      <input id={fieldId('vel-on')} type="number" class="input-cc-value" class:error={!!velocityOnError}
        value={button.velocity_on !== undefined ? button.velocity_on : ''} onblur={handleVelocityOnChange}
        disabled={disabled} min="0" max="127" placeholder="127" />
      {#if velocityOnError}<span class="error-text">{velocityOnError}</span>{/if}
    </div>
    <div class="field">
      <label class="field-label" for={fieldId('vel-off')}>Vel OFF:</label>
      <input id={fieldId('vel-off')} type="number" class="input-cc-value" class:error={!!velocityOffError}
        value={button.velocity_off !== undefined ? button.velocity_off : ''} onblur={handleVelocityOffChange}
        disabled={disabled} min="0" max="127" placeholder="0" />
      {#if velocityOffError}<span class="error-text">{velocityOffError}</span>{/if}
    </div>
  {:else if isPC}
    <div class="field">
      <label class="field-label" for={fieldId('program')}>Program:</label>
      <input id={fieldId('program')} type="number" class="input-cc" class:error={!!programError}
        value={button.program ?? 0} onblur={handleProgramChange} disabled={disabled}
        min="0" max="127" />
      {#if programError}<span class="error-text">{programError}</span>{/if}
    </div>
  {:else if isPCIncDec}
    <div class="field">
      <label class="field-label" for={fieldId('pc-step')}>Step:</label>
      <input id={fieldId('pc-step')} type="number" class="input-cc" class:error={!!pcStepError}
        value={button.pc_step ?? 1} onblur={handlePCStepChange} disabled={disabled}
        min="1" max="127" />
      {#if pcStepError}<span class="error-text">{pcStepError}</span>{/if}
    </div>
  {/if}

  {#if isPC || isPCIncDec}
    <div class="field">
      <label class="field-label" for={fieldId('flash-ms')}>Flash (ms):</label>
      <input id={fieldId('flash-ms')} type="number" class="input-cc" class:error={!!flashMsError}
        value={button.flash_ms ?? ''} onblur={handleFlashMsChange} disabled={disabled}
        min="50" max="5000" step="50" placeholder="200" />
      {#if flashMsError}<span class="error-text">{flashMsError}</span>{/if}
    </div>
  {/if}

  <div class="field">
    <label class="field-label" for={fieldId('keytimes')}>Keytimes:</label>
    <input
      id={fieldId('keytimes')}
      type="number"
      class="input-cc"
      class:error={!!keytimesError}
      value={button.keytimes ?? 1}
      onblur={handleKeytimesChange}
      disabled={disabled}
      min="1"
      max="99"
    />
    {#if keytimesError}<span class="error-text">{keytimesError}</span>{/if}
  </div>

  <div class="field">
    <span class="field-label">LED Color:</span>
    <ColorSelect
      value={button.color}
      onchange={handleColorChange}
    />
  </div>

  {#if showMode}
    <div class="field">
      <label class="field-label" for={fieldId('mode')}>Switch Mode:</label>
      <select id={fieldId('mode')} class="select" value={button.mode || 'toggle'} onchange={handleModeChange} disabled={disabled}>
        <option value="toggle">Toggle</option>
        <option value="momentary">Momentary</option>
      </select>
    </div>
  {/if}

  <div class="field">
    <label class="field-label" for={fieldId('off-mode')}>LED Off Mode:</label>
    <select id={fieldId('off-mode')} class="select" value={button.off_mode || 'dim'} onchange={handleOffModeChange} disabled={disabled}>
      <option value="dim">Dim</option>
      <option value="off">Off</option>
    </select>
  </div>

  {#if hasKeytimes && !disabled}
    <div class="states-section">
      <span class="states-label">States ({button.states?.length ?? 0}):</span>
      {#each (button.states ?? []) as state, si}
        <div class="state-row">
          <span class="state-num">S{si + 1}:</span>

          {#if isCC}
            <div class="field">
              <label class="field-label" for={stateFieldId(si, 'cc')}>CC:</label>
              <input id={stateFieldId(si, 'cc')} type="number" class="input-cc" class:error={!!stateError(si, 'cc')}
                value={state.cc !== undefined ? state.cc : ''}
                onblur={(e) => handleStateFieldChange(si, 'cc', e)}
                min="0" max="127" placeholder={String(button.cc ?? '')} />
              {#if stateError(si, 'cc')}<span class="error-text">{stateError(si, 'cc')}</span>{/if}
            </div>
            <div class="field">
              <label class="field-label" for={stateFieldId(si, 'cc-on')}>ON Val:</label>
              <input id={stateFieldId(si, 'cc-on')} type="number" class="input-cc-value" class:error={!!stateError(si, 'cc_on')}
                value={state.cc_on !== undefined ? state.cc_on : ''}
                onblur={(e) => handleStateFieldChange(si, 'cc_on', e)}
                min="0" max="127" placeholder={String(button.cc_on ?? 127)} />
              {#if stateError(si, 'cc_on')}<span class="error-text">{stateError(si, 'cc_on')}</span>{/if}
            </div>
            <div class="field">
              <label class="field-label" for={stateFieldId(si, 'cc-off')}>OFF Val:</label>
              <input id={stateFieldId(si, 'cc-off')} type="number" class="input-cc-value" class:error={!!stateError(si, 'cc_off')}
                value={state.cc_off !== undefined ? state.cc_off : ''}
                onblur={(e) => handleStateFieldChange(si, 'cc_off', e)}
                min="0" max="127" placeholder={String(button.cc_off ?? 0)} />
              {#if stateError(si, 'cc_off')}<span class="error-text">{stateError(si, 'cc_off')}</span>{/if}
            </div>
          {:else if isNote}
            <div class="field">
              <label class="field-label" for={stateFieldId(si, 'note')}>Note:</label>
              <input id={stateFieldId(si, 'note')} type="number" class="input-cc" class:error={!!stateError(si, 'note')}
                value={state.note !== undefined ? state.note : ''}
                onblur={(e) => handleStateFieldChange(si, 'note', e)}
                min="0" max="127" placeholder={String(button.note ?? 60)} />
              {#if stateError(si, 'note')}<span class="error-text">{stateError(si, 'note')}</span>{/if}
            </div>
            <div class="field">
              <label class="field-label" for={stateFieldId(si, 'vel-on')}>Vel ON:</label>
              <input id={stateFieldId(si, 'vel-on')} type="number" class="input-cc-value" class:error={!!stateError(si, 'velocity_on')}
                value={state.velocity_on !== undefined ? state.velocity_on : ''}
                onblur={(e) => handleStateFieldChange(si, 'velocity_on', e)}
                min="0" max="127" placeholder={String(button.velocity_on ?? 127)} />
              {#if stateError(si, 'velocity_on')}<span class="error-text">{stateError(si, 'velocity_on')}</span>{/if}
            </div>
            <div class="field">
              <label class="field-label" for={stateFieldId(si, 'vel-off')}>Vel OFF:</label>
              <input id={stateFieldId(si, 'vel-off')} type="number" class="input-cc-value" class:error={!!stateError(si, 'velocity_off')}
                value={state.velocity_off !== undefined ? state.velocity_off : ''}
                onblur={(e) => handleStateFieldChange(si, 'velocity_off', e)}
                min="0" max="127" placeholder={String(button.velocity_off ?? 0)} />
              {#if stateError(si, 'velocity_off')}<span class="error-text">{stateError(si, 'velocity_off')}</span>{/if}
            </div>
          {:else if isPC}
            <div class="field">
              <label class="field-label" for={stateFieldId(si, 'program')}>Program:</label>
              <input id={stateFieldId(si, 'program')} type="number" class="input-cc" class:error={!!stateError(si, 'program')}
                value={state.program !== undefined ? state.program : ''}
                onblur={(e) => handleStateFieldChange(si, 'program', e)}
                min="0" max="127" placeholder={String(button.program ?? 0)} />
              {#if stateError(si, 'program')}<span class="error-text">{stateError(si, 'program')}</span>{/if}
            </div>
          {:else if isPCIncDec}
            <div class="field">
              <label class="field-label" for={stateFieldId(si, 'pc-step')}>Step:</label>
              <input id={stateFieldId(si, 'pc-step')} type="number" class="input-cc" class:error={!!stateError(si, 'pc_step')}
                value={state.pc_step !== undefined ? state.pc_step : ''}
                onblur={(e) => handleStateFieldChange(si, 'pc_step', e)}
                min="1" max="127" placeholder={String(button.pc_step ?? 1)} />
              {#if stateError(si, 'pc_step')}<span class="error-text">{stateError(si, 'pc_step')}</span>{/if}
            </div>
          {/if}

          <div class="field">
            <span class="field-label">Color:</span>
            <ColorSelect
              value={state.color ?? button.color}
              onchange={(color) => handleStateColorChange(si, color)}
            />
          </div>
          <div class="field">
            <label class="field-label" for={stateFieldId(si, 'label')}>Label:</label>
            <input id={stateFieldId(si, 'label')} type="text" class="input-label" class:error={!!stateError(si, 'label')}
              value={state.label ?? ''}
              onblur={(e) => handleStateLabelChange(si, e)}
              maxlength="6"
              placeholder={button.label} />
            {#if stateError(si, 'label')}<span class="error-text">{stateError(si, 'label')}</span>{/if}
          </div>
        </div>
      {/each}
    </div>
  {/if}

  {#if disabled}
    <div class="disabled-overlay">
      Not available on this device
    </div>
  {/if}
</div>

<style>
  .button-row {
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
    padding: 0.5rem;
    border: 1px solid #e5e5e5;
    border-radius: 4px;
    margin-bottom: 0.5rem;
    position: relative;
    flex-wrap: wrap;
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

  .visually-hidden {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
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

  .input-channel {
    width: 60px;
    padding: 0.375rem 0.5rem;
    border: 1px solid #ccc;
    border-radius: 4px;
    font-size: 0.875rem;
  }

  .input-cc-value {
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

  input.error {
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

  .states-section {
    width: 100%;
    margin-top: 0.5rem;
    padding-top: 0.5rem;
    border-top: 1px dashed #e0e0e0;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .states-label {
    font-size: 0.75rem;
    font-weight: 600;
    color: #555;
    margin-bottom: 0.25rem;
  }

  .state-row {
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
    flex-wrap: wrap;
    padding: 0.25rem 0.5rem;
    background: #fafafa;
    border: 1px solid #eee;
    border-radius: 4px;
  }

  .state-num {
    font-size: 0.75rem;
    color: #888;
    min-width: 28px;
    padding-top: 1.5rem;
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
