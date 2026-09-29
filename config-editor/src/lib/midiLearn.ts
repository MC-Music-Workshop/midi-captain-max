// MIDI Learn (#54): assign a button from the next message the device receives.
import { writable } from 'svelte/store';
import { learnMidi, cancelMidiLearn, type LearnedMidi } from './api';
import type { ButtonConfig } from './types';

const NUMBER_FIELD = { cc: 'cc', note: 'note', pc: 'program' } as const;

/**
 * Field writes that make `button` send `msg`. Only the message identity is
 * learned (type, channel, number); CC on/off values and velocities stay as
 * configured, since an incoming 0 or NoteOff says nothing about them.
 */
export function learnedFieldUpdates(button: ButtonConfig, msg: LearnedMidi): [string, unknown][] {
  const updates: [string, unknown][] = [
    ['type', msg.type],
    ['channel', msg.channel],
    [NUMBER_FIELD[msg.type], msg.number],
  ];
  // Keep Mode on a value the new type offers: flash is PC-only, select is PC/CC-only.
  if ((button.mode === 'flash' && msg.type !== 'pc') || (button.mode === 'select' && msg.type === 'note')) {
    updates.push(['mode', 'toggle']);
  }
  return updates;
}

export function describeLearned(msg: LearnedMidi): string {
  const what = msg.type === 'cc' ? `CC${msg.number}` : msg.type === 'note' ? `Note ${msg.number}` : `PC${msg.number}`;
  return `${what} on Ch${msg.channel + 1} (${msg.source})`;
}

/** Index of the button that is listening, or null. One at a time: the device has one console. */
export const learningButton = writable<number | null>(null);

let active: Promise<LearnedMidi | null> | null = null;

/** Listen for the next message on behalf of button `index`. Null means cancelled. */
export async function startLearn(path: string, index: number): Promise<LearnedMidi | null> {
  // The previous listener must release the serial port before a new one opens it.
  await cancelLearn();
  learningButton.set(index);
  const run = learnMidi(path);
  active = run;
  try {
    return await run;
  } finally {
    if (active === run) {
      active = null;
      learningButton.set(null);
    }
  }
}

export async function cancelLearn(): Promise<void> {
  const run = active;
  if (!run) return;
  await cancelMidiLearn();
  await run.catch(() => {});
}
