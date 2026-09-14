<script lang="ts">
  import Accordion from './Accordion.svelte';
  import { config, updateField } from '$lib/formStore';

  // Defaults: cross-thru on, DIN->DIN on (classic MIDI THRU), USB->USB off (loopback risk).
  let usbToDin = $derived($config.midi_thru_usb_to_din ?? true);
  let dinToUsb = $derived($config.midi_thru_din_to_usb ?? true);
  let dinToDin = $derived($config.midi_thru_din_to_din ?? true);
  let usbToUsb = $derived($config.midi_thru_usb_to_usb ?? false);

  // Local routes: where this pedal's own messages go, and which inputs it acts
  // on. All default on -- every port live, as before the matrix grew.
  let localToUsb = $derived($config.midi_local_to_usb ?? true);
  let localToDin = $derived($config.midi_local_to_din ?? true);
  let usbToLocal = $derived($config.midi_usb_to_local ?? true);
  let dinToLocal = $derived($config.midi_din_to_local ?? true);

  let sendsNothing = $derived(!localToUsb && !localToDin);
  let hearsNothing = $derived(!usbToLocal && !dinToLocal);

  function onChange(field: string, e: Event) {
    const target = e.target as HTMLInputElement;
    updateField(field, target.checked);
  }
</script>

<Accordion title="MIDI Routing">
  <div class="midi-thru-section">
    <p class="section-help">
      Route MIDI between the USB port, the 5-pin DIN port, and this pedal itself.
      Each cell controls one path from a source (row) to a destination (column).
      Cross-thru, DIN&nbsp;→&nbsp;DIN (classic MIDI THRU) and every path to and
      from this pedal are on by default.
    </p>

    <table class="thru-matrix" aria-label="MIDI routing matrix">
      <thead>
        <tr>
          <th scope="col" class="corner">From&nbsp;\&nbsp;To</th>
          <th scope="col">USB</th>
          <th scope="col">5-pin DIN</th>
          <th scope="col">This pedal</th>
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
          <td>
            <label class="cell">
              <input
                type="checkbox"
                checked={usbToLocal}
                onchange={(e) => onChange('midi_usb_to_local', e)}
              />
              <span>USB → pedal</span>
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
          <td>
            <label class="cell">
              <input
                type="checkbox"
                checked={dinToLocal}
                onchange={(e) => onChange('midi_din_to_local', e)}
              />
              <span>DIN → pedal</span>
            </label>
          </td>
        </tr>
        <tr>
          <th scope="row">This pedal</th>
          <td>
            <label class="cell">
              <input
                type="checkbox"
                checked={localToUsb}
                onchange={(e) => onChange('midi_local_to_usb', e)}
              />
              <span>pedal → USB</span>
            </label>
          </td>
          <td>
            <label class="cell">
              <input
                type="checkbox"
                checked={localToDin}
                onchange={(e) => onChange('midi_local_to_din', e)}
              />
              <span>pedal → DIN</span>
            </label>
          </td>
          <!-- A pedal "routing to itself" is just the button doing its job. -->
          <td class="na" aria-label="not applicable">—</td>
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

    {#if sendsNothing}
      <div class="warning" role="alert">
        <strong>⚠ This pedal's switches send nothing.</strong>
        Both of its outputs are off, so button, encoder and expression messages
        go nowhere. Turn on at least one of <em>pedal&nbsp;→&nbsp;USB</em> or
        <em>pedal&nbsp;→&nbsp;DIN</em>.
      </div>
    {/if}

    {#if hearsNothing}
      <div class="warning" role="alert">
        <strong>⚠ This pedal ignores all incoming MIDI.</strong>
        Both inputs are forward-only, so nothing will match buttons, update LEDs
        or track select groups. Thru still passes messages along.
      </div>
    {/if}

    <details class="routing-help">
      <summary>What does each route do?</summary>
      <ul>
        <li><strong>USB → DIN:</strong> forward MIDI from the computer to gear plugged into the 5-pin DIN output.</li>
        <li><strong>DIN → USB:</strong> forward MIDI from a 5-pin source (e.g. another foot controller) to the computer.</li>
        <li><strong>DIN → DIN:</strong> classic MIDI THRU. Forward incoming 5-pin MIDI to the 5-pin output for daisy-chaining controllers downstream.</li>
        <li><strong>USB → USB:</strong> echo USB MIDI back to the host. Niche; off by default to avoid feedback with DAW MIDI echo.</li>
        <li><strong>USB / DIN → pedal:</strong> act on messages arriving on that port — match buttons, drive LEDs, track select groups. Turn off to make the port forward-only.</li>
        <li><strong>pedal → USB / DIN:</strong> send this pedal's own button, encoder and expression messages out that port.</li>
      </ul>
      <p class="ring-note">
        <strong>MIDI ring setups:</strong> if this pedal's DIN output feeds a chain
        that loops back into its own DIN input, turn off <em>DIN&nbsp;→&nbsp;DIN</em>
        (so messages don't circulate forever), <em>pedal&nbsp;→&nbsp;DIN</em> (so its
        own messages don't lap the ring and reach the host twice) and
        <em>DIN&nbsp;→&nbsp;pedal</em> (so it doesn't act twice on what the host
        already sent it over USB).
      </p>
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

  .thru-matrix .na {
    background: var(--surface-muted, #f8f8f8);
    color: var(--text-secondary, #aaa);
    text-align: center;
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

  .ring-note {
    margin: 0.75rem 0 0 0;
    line-height: 1.5;
  }
</style>
