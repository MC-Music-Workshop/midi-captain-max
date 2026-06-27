<script lang="ts">
  import Accordion from './Accordion.svelte';
  import ButtonRow from './ButtonRow.svelte';
  import { config, currentPage, updateField } from '$lib/formStore';
  import type { DeviceType } from '$lib/types';

  // Device-specific button names (default: "Button 1", "Button 2", etc.)
  const DEVICE_BUTTON_NAMES: Partial<Record<DeviceType, string[]>> = {
    one1: ['KEY0'],
    duo2: ['KEY0', 'KEY1'],
  };

  let deviceType = $derived($config.device);
  let buttons = $derived($currentPage.buttons);
  let globalChannel = $derived($config.global_channel ?? 0);
  let visibleCount = $derived(buttons.length);
  let buttonNames = $derived(DEVICE_BUTTON_NAMES[deviceType ?? 'std10']);
  
  function handleButtonUpdate(index: number, field: string, value: any) {
    updateField(`buttons[${index}].${field}`, value);
  }
</script>

<Accordion title="Buttons ({visibleCount} of {visibleCount})">
  <div class="buttons-list">
    {#each buttons as button, index}
      {@const isDisabled = (deviceType === 'one1' && index >= 1) || (deviceType === 'duo2' && index >= 2) || (deviceType === 'nano4' && index >= 4) || (deviceType === 'mini6' && index >= 6)}
      <ButtonRow
        {button}
        {index}
        displayName={buttonNames?.[index]}
        disabled={isDisabled}
        globalChannel={globalChannel}
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
