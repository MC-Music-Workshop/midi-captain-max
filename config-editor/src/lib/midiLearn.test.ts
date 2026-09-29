import { describe, it, expect, vi } from 'vitest';
import { get } from 'svelte/store';
import type { LearnedMidi } from './api';

// Stand-in for the Rust side: learn_midi resolves with whatever `pending.resolve` is
// given, and cancel_midi_learn resolves the in-flight learn with null.
let pending: { resolve: (m: LearnedMidi | null) => void } | null = null;
vi.mock('./api', () => ({
  learnMidi: vi.fn(() => new Promise((resolve) => { pending = { resolve }; })),
  cancelMidiLearn: vi.fn(async () => { pending?.resolve(null); }),
}));

const { learnedFieldUpdates, describeLearned, startLearn, cancelLearn, learningButton } = await import('./midiLearn');

// Let the chained awaits inside startLearn/cancelLearn settle.
const settle = () => new Promise((r) => setTimeout(r, 0));

const msg = (type: LearnedMidi['type'], number: number, channel = 0): LearnedMidi =>
  ({ type, channel, number, value: null, source: 'USB' });

describe('learnedFieldUpdates', () => {
  it('sets type, channel and the type-specific number field', () => {
    expect(learnedFieldUpdates({ label: 'A', color: 'red' }, msg('cc', 20, 3))).toEqual([['type', 'cc'], ['channel', 3], ['cc', 20]]);
    expect(learnedFieldUpdates({ label: 'A', color: 'red' }, msg('note', 60))).toEqual([['type', 'note'], ['channel', 0], ['note', 60]]);
    expect(learnedFieldUpdates({ label: 'A', color: 'red' }, msg('pc', 5))).toEqual([['type', 'pc'], ['channel', 0], ['program', 5]]);
  });

  it('drops a mode the learned type does not offer', () => {
    expect(learnedFieldUpdates({ label: 'A', color: 'red', type: 'pc', mode: 'flash' }, msg('cc', 1))).toContainEqual(['mode', 'toggle']);
    expect(learnedFieldUpdates({ label: 'A', color: 'red', type: 'cc', mode: 'select' }, msg('note', 1))).toContainEqual(['mode', 'toggle']);
  });

  it('keeps a mode the learned type offers', () => {
    const keeps = (mode: 'flash' | 'select' | 'momentary', type: LearnedMidi['type']) =>
      learnedFieldUpdates({ label: 'A', color: 'red', mode }, msg(type, 1)).some(([f]) => f === 'mode');
    expect(keeps('flash', 'pc')).toBe(false);
    expect(keeps('select', 'cc')).toBe(false);
    expect(keeps('select', 'pc')).toBe(false);
    expect(keeps('momentary', 'note')).toBe(false);
  });
});

describe('describeLearned', () => {
  it('names the message in 1-16 channel terms', () => {
    expect(describeLearned({ ...msg('cc', 20, 0), source: 'DIN' })).toBe('CC20 on Ch1 (DIN)');
  });
});

describe('startLearn', () => {
  it('tracks the listening button and clears it when a message arrives', async () => {
    const run = startLearn('/Volumes/MIDICAPTAIN/config.json', 2);
    await settle();
    expect(get(learningButton)).toBe(2);
    pending!.resolve(msg('pc', 7));
    expect(await run).toEqual(msg('pc', 7));
    expect(get(learningButton)).toBe(null);
  });

  it('cancels the previous listener before a second button starts', async () => {
    const first = startLearn('/p', 0);
    await settle();
    const second = startLearn('/p', 1);
    expect(await first).toBe(null);
    await settle();
    expect(get(learningButton)).toBe(1);
    await cancelLearn();
    expect(await second).toBe(null);
    expect(get(learningButton)).toBe(null);
  });
});
