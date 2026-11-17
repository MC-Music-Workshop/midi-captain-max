import { describe, it, expect } from 'vitest';
import { firmwareSync, needsFirmwareNotice, parseVersion } from './firmwareSync';

const sync = (device: string | null, bundled: string) => firmwareSync({ device, bundled });

describe('firmwareSync', () => {
  it('matches identical versions', () => {
    expect(sync('v1.15.0', 'v1.15.0')).toBe('match');
    expect(sync('dev', 'dev')).toBe('match');
  });

  it('flags a pedal behind the editor', () => {
    expect(sync('v1.14.0', 'v1.15.0')).toBe('older');
    expect(sync('v1.15.0-beta.2', 'v1.15.0-beta.3')).toBe('older');
    expect(sync('v1.15.0-alpha.4', 'v1.15.0-beta.1')).toBe('older');
    expect(sync('v1.15.0-rc.1', 'v1.15.0')).toBe('older');
    expect(sync('v1.9.0', 'v1.10.0')).toBe('older');
  });

  it('does not flag a pedal ahead of the editor', () => {
    expect(sync('v1.15.0', 'v1.14.0')).toBe('newer');
    expect(sync('v1.15.0', 'v1.15.0-beta.3')).toBe('newer');
    // Dev deploy (git describe) past the editor's tag.
    expect(sync('v1.15.0-3-gfcf10e3', 'v1.15.0')).toBe('newer');
  });

  it('treats a dev build behind the tag the same way', () => {
    expect(sync('v1.14.0-7-gabc1234', 'v1.15.0')).toBe('older');
  });

  it('reports a pedal without VERSION.txt as unmanaged', () => {
    expect(sync(null, 'v1.15.0')).toBe('unmanaged');
  });

  it('gives up on versions it cannot compare', () => {
    expect(sync('v1.15.0', 'dev')).toBe('unknown');
    expect(sync('fcf10e3', 'v1.15.0')).toBe('unknown');
  });
});

describe('needsFirmwareNotice', () => {
  it('shows the notice only when the pedal is behind or unmanaged', () => {
    expect(needsFirmwareNotice('older')).toBe(true);
    expect(needsFirmwareNotice('unmanaged')).toBe(true);
    for (const s of ['match', 'newer', 'unknown'] as const) {
      expect(needsFirmwareNotice(s)).toBe(false);
    }
  });
});

describe('parseVersion', () => {
  it('accepts versions with or without the v prefix', () => {
    expect(parseVersion('1.15.0')).toEqual(parseVersion('v1.15.0'));
  });

  it('reads prerelease and git describe suffixes', () => {
    expect(parseVersion('v1.15.0-beta.3-2-gabc1234')).toEqual({ nums: [1, 15, 0], pre: [1, 3], ahead: 2 });
  });
});
