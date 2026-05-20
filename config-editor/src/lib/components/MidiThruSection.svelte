<script lang="ts">
  import Accordion from './Accordion.svelte';
  import { config, updateField } from '$lib/formStore';

  // Defaults: cross-thru on, DIN->DIN on (classic MIDI THRU), USB->USB off (loopback risk).
  let usbToDin = $derived($config.midi_thru_usb_to_din ?? true);
  let dinToUsb = $derived($config.midi_thru_din_to_usb ?? true);
  let dinToDin = $derived($config.midi_thru_din_to_din ?? true);
  let usbToUsb = $derived($config.midi_thru_usb_to_usb ?? false);

  function onChange(field: string, e: Event) {
    const target = e.target as HTMLInputElement;
    updateField(field, target.checked);
  }
</script>

<Accordion title="MIDI Thru">
  <div class="midi-thru-section">
    <p class="section-help">
      Route incoming MIDI between USB and 5-pin DIN ports. Each cell of the matrix
      controls one path from an input (row) to an output (column). Cross-thru and
      DIN&nbsp;→&nbsp;DIN (classic MIDI THRU pass-through) are on by default.
    </p>

    <table class="thru-matrix" aria-label="MIDI Thru routing matrix">
      <thead>
        <tr>
          <th scope="col" class="corner">From&nbsp;\&nbsp;To</th>
          <th scope="col">USB</th>
          <th scope="col">5-pin DIN</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <th scope="row">USB</th>
          <td>
            <label class="cell">
              <input
                type="checkbox"
                checked={usbToUsb}
                onchange={(e) => onChange('midi_thru_usb_to_usb', e)}
              />
              <span>USB → USB</span>
            </label>
          </td>
          <td>
            <label class="cell">
              <input
                type="checkbox"
                checked={usbToDin}
                onchange={(e) => onChange('midi_thru_usb_to_din', e)}
              />
              <span>USB → DIN</span>
            </label>
          </td>
        </tr>
        <tr>
          <th scope="row">5-pin DIN</th>
          <td>
            <label class="cell">
              <input
                type="checkbox"
                checked={dinToUsb}
                onchange={(e) => onChange('midi_thru_din_to_usb', e)}
              />
              <span>DIN → USB</span>
            </label>
          </td>
          <td>
            <label class="cell">
              <input
                type="checkbox"
                checked={dinToDin}
                onchange={(e) => onChange('midi_thru_din_to_din', e)}
              />
              <span>DIN → DIN</span>
            </label>
          </td>
        </tr>
      </tbody>
    </table>

    {#if usbToUsb}
      <div class="warning" role="alert">
        <strong>⚠ USB loopback enabled.</strong>
        Messages received on USB MIDI will be echoed back to the host. If your
        DAW also has MIDI echo / through enabled on the same port, this will
        cause duplicate notes or a feedback loop. Most users should leave this off.
      </div>
    {/if}

    <details class="routing-help">
      <summary>What does each route do?</summary>
      <ul>
        <li><strong>USB → DIN:</strong> forward MIDI from the computer to gear plugged into the 5-pin DIN output.</li>
        <li><strong>DIN → USB:</strong> forward MIDI from a 5-pin source (e.g. another foot controller) to the computer.</li>
        <li><strong>DIN → DIN:</strong> classic MIDI THRU. Forward incoming 5-pin MIDI to the 5-pin output for daisy-chaining controllers downstream.</li>
        <li><strong>USB → USB:</strong> echo USB MIDI back to the host. Niche; off by default to avoid feedback with DAW MIDI echo.</li>
      </ul>
    </details>
  </div>
</Accordion>

<style>
  .midi-thru-section {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .section-help {
    font-size: 0.875rem;
    color: var(--text-secondary, #666);
    margin: 0 0 0.25rem 0;
  }

  .thru-matrix {
    border-collapse: collapse;
    align-self: flex-start;
    font-size: 0.9rem;
  }

  .thru-matrix th,
  .thru-matrix td {
    border: 1px solid var(--border, #d0d0d0);
    padding: 0.5rem 0.75rem;
    text-align: left;
  }

  .thru-matrix thead th {
    background: var(--surface-muted, #f3f3f3);
    font-weight: 600;
  }

  .thru-matrix tbody th {
    background: var(--surface-muted, #f8f8f8);
    font-weight: 600;
  }

  .thru-matrix .corner {
    background: transparent;
    border: none;
    font-weight: 500;
    color: var(--text-secondary, #888);
  }

  .cell {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    cursor: pointer;
  }

  .cell input[type='checkbox'] {
    width: 16px;
    height: 16px;
    cursor: pointer;
  }

  .warning {
    border: 1px solid #c89200;
    background: #fff7e0;
    color: #5a4400;
    padding: 0.6rem 0.8rem;
    border-radius: 4px;
    font-size: 0.875rem;
    line-height: 1.4;
  }

  .routing-help {
    font-size: 0.875rem;
    color: var(--text-secondary, #555);
  }

  .routing-help summary {
    cursor: pointer;
    font-weight: 500;
  }

  .routing-help ul {
    margin: 0.5rem 0 0 1.25rem;
    padding: 0;
  }

  .routing-help li {
    margin-bottom: 0.25rem;
  }
</style>
