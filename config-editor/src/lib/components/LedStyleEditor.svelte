<script lang="ts">
  // Per-LED colors + animation for one switch state (led_on / led_off on a button,
  // `led` on a keytimes entry). Each switch has three LEDs. Without custom colors the
  // state's usual color fills all three, so an animation can be added on its own.
  import type { CycleEntryColor, LedAnimation, LedStyle } from '$lib/types';
  import { BUTTON_COLORS, LED_ANIMATION_LABELS } from '$lib/types';
  import { validationErrors, normalizeLedStyle } from '$lib/formStore';
  import { LED_SPEED_MS_DEFAULT, LED_SPEED_MS_MIN, LED_SPEED_MS_MAX } from '$lib/validation';

  interface Props {
    // Unique DOM id prefix, e.g. "btn-3-led-on" or "btn-3-short-0-led".
    idPrefix: string;
    legend: string;
    style: LedStyle | undefined;
    // What the three LEDs show for this state without custom colors. Also seeds
    // the pickers when "Custom colors" is ticked.
    fallbackPixels: CycleEntryColor[];
    // Colors "Custom colors" starts from, when they differ from the fallback look
    // (an off state whose fallback is dark). Default: fallbackPixels.
    seedPixels?: CycleEntryColor[];
    // Preview only: the fallback look is dimmed (off_mode dim / keytimes entry dim).
    fallbackDim?: boolean;
    // Preview only: custom pixels are dimmed too (keytimes entry dim).
    pixelsDim?: boolean;
    // Config path of this style; prefixes validation error keys.
    errorPath: string;
    disabled?: boolean;
    title?: string;
    onchange: (style: LedStyle | undefined) => void;
  }

  let { idPrefix, legend, style, fallbackPixels, seedPixels, fallbackDim = false, pixelsDim = false,
        errorPath, disabled = false, title, onchange }: Props = $props();

  const PIXEL_COLORS: CycleEntryColor[] = [
    'red', 'green', 'blue', 'yellow', 'cyan', 'magenta', 'orange', 'purple', 'white', 'off',
  ];
  const ANIMATIONS = Object.keys(LED_ANIMATION_LABELS) as LedAnimation[];

  let pixels = $derived(style?.pixels);
  let animation = $derived<LedAnimation>(style?.animation ?? 'solid');
  let moving = $derived(animation !== 'solid');
  let speedMs = $derived(style?.speed_ms ?? LED_SPEED_MS_DEFAULT);

  let pixelsError = $derived($validationErrors.get(`${errorPath}.pixels`));
  let animationError = $derived($validationErrors.get(`${errorPath}.animation`));
  let speedError = $derived($validationErrors.get(`${errorPath}.speed_ms`));

  // Every write goes through the save shape: no 'solid', no speed without a
  // moving animation, and an all-default style becomes undefined (field removed).
  function write(next: LedStyle) {
    onchange(normalizeLedStyle(next));
  }

  function setCustom(on: boolean) {
    const src = seedPixels ?? fallbackPixels;
    const seeded = [src[0], src[1], src[2]] as NonNullable<LedStyle['pixels']>;
    write({ ...style, pixels: on ? seeded : undefined });
  }

  function setPixel(i: number, color: CycleEntryColor) {
    if (!pixels) return;
    const next = [...pixels] as NonNullable<LedStyle['pixels']>;
    next[i] = color;
    write({ ...style, pixels: next });
  }

  function setAnimation(a: LedAnimation) {
    write({ ...style, animation: a });
  }

  function setSpeed(e: Event) {
    const v = (e.target as HTMLInputElement).value;
    const n = v === '' ? undefined : Number(v);
    write({ ...style, speed_ms: n === undefined || Number.isNaN(n) ? undefined : n });
  }

  // --- Preview: the same frames the firmware renders (core/led_style.py) ---
  let base = $derived<CycleEntryColor[]>(pixels ?? fallbackPixels);
  let baseDim = $derived(pixels ? pixelsDim : fallbackDim);
  let dark = $derived(base.every((c) => c === 'off'));
  let frames = $derived.by<CycleEntryColor[][]>(() => {
    if (!moving || dark) return [base];
    if (animation === 'flash') return [base, ['off', 'off', 'off']];
    const p = base[0] === base[1] && base[1] === base[2] ? [base[0], 'off', 'off'] as CycleEntryColor[] : base;
    return [p, [p[2], p[0], p[1]], [p[1], p[2], p[0]]];
  });

  let tick = $state(0);
  $effect(() => {
    if (frames.length <= 1) return;
    const ms = Math.min(LED_SPEED_MS_MAX, Math.max(LED_SPEED_MS_MIN, speedMs || LED_SPEED_MS_DEFAULT));
    const id = setInterval(() => { tick += 1; }, ms);
    return () => clearInterval(id);
  });
  let shown = $derived(frames[tick % frames.length]);

  function cssColor(c: CycleEntryColor): string {
    return c === 'off' ? '#222' : BUTTON_COLORS[c];
  }
</script>

<fieldset class="led-style" {title}>
  <legend class="led-legend">{legend}</legend>

  <span class="led-preview" aria-hidden="true">
    {#each shown as c, i (i)}
      <span class="led-dot" class:dim={baseDim && c !== 'off'} style="background: {cssColor(c)}"></span>
    {/each}
  </span>

  <label class="inline" for={`${idPrefix}-custom`}
         title="Pick each of the three LEDs' color. Unticked, the state's usual color fills all three.">
    <input id={`${idPrefix}-custom`} type="checkbox" checked={pixels !== undefined} {disabled}
           onchange={(e) => setCustom((e.target as HTMLInputElement).checked)} />
    Custom colors
  </label>

  {#if pixels}
    {#each [0, 1, 2] as i (i)}
      <label class="visually-hidden" for={`${idPrefix}-pixel-${i}`}>{legend} LED {i + 1} color</label>
      <select id={`${idPrefix}-pixel-${i}`} class="led-select" class:error={!!pixelsError}
              value={pixels[i]} {disabled} title={`LED ${i + 1}`}
              onchange={(e) => setPixel(i, (e.target as HTMLSelectElement).value as CycleEntryColor)}>
        {#each PIXEL_COLORS as c}
          <option value={c}>{c}</option>
        {/each}
      </select>
    {/each}
  {/if}

  <label class="inline" for={`${idPrefix}-animation`}>Animation:</label>
  <select id={`${idPrefix}-animation`} class="led-select" class:error={!!animationError}
          value={animation} {disabled}
          title="Solid: steady. Flash: blinks on and off. Spin: the colors rotate around the ring (one color spins as a single lit LED)."
          onchange={(e) => setAnimation((e.target as HTMLSelectElement).value as LedAnimation)}>
    {#each ANIMATIONS as a}
      <option value={a}>{LED_ANIMATION_LABELS[a]}</option>
    {/each}
  </select>

  {#if moving}
    <label class="inline" for={`${idPrefix}-speed`}>Speed (ms):</label>
    <input id={`${idPrefix}-speed`} type="number" class="led-speed" class:error={!!speedError}
           min={LED_SPEED_MS_MIN} max={LED_SPEED_MS_MAX} step="10"
           value={style?.speed_ms ?? ''} placeholder={String(LED_SPEED_MS_DEFAULT)} {disabled}
           title="Flash: on time (and off time). Spin: time per position. 50-5000 ms, default 250."
           onchange={setSpeed} />
  {/if}

  {#if pixelsError || animationError || speedError}
    <span class="led-error">{pixelsError ?? animationError ?? speedError}</span>
  {/if}
</fieldset>

<style>
  .led-style {
    display: inline-flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.375rem;
    margin: 0;
    padding: 0.25rem 0.5rem;
    border: 1px solid #d8dde5;
    border-radius: 4px;
    font-size: 0.8125rem;
  }

  .led-legend {
    font-size: 0.75rem;
    color: #666;
    padding: 0 0.25rem;
  }

  .led-preview {
    display: inline-flex;
    gap: 3px;
    padding: 2px 4px;
    background: #333;
    border-radius: 8px;
  }

  .led-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    border: 1px solid #555;
  }

  .led-dot.dim {
    opacity: 0.35;
  }

  label.inline {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    color: #444;
  }

  .led-select, .led-speed {
    padding: 0.125rem 0.25rem;
    border: 1px solid #bbb;
    border-radius: 3px;
    font-size: 0.8125rem;
    background: white;
  }

  .led-speed {
    width: 4.5rem;
  }

  .error {
    border-color: #c00;
    background: #fef0f0;
  }

  .led-error {
    flex-basis: 100%;
    color: #c00;
    font-size: 0.75rem;
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
</style>
