// Is the pedal's firmware in step with the firmware this editor ships (#192)?
// Pure so the rules can be tested without a device.
import type { FirmwareVersions } from './types';

/**
 * - `match`: same version.
 * - `older`: the pedal is behind the editor; new features may not work. Warn.
 * - `newer`: the pedal is ahead (dev deploys, or an older editor). Don't nag.
 * - `unmanaged`: no VERSION.txt on the pedal (OEM or bare CircuitPython). Offer install.
 * - `unknown`: a version we can't compare (e.g. `dev`). Don't nag.
 */
export type FirmwareSync = 'match' | 'older' | 'newer' | 'unmanaged' | 'unknown';

interface ParsedVersion {
  nums: [number, number, number];
  // [rank, n] for alpha/beta/rc; null for a final release (ranks above all prereleases).
  pre: [number, number] | null;
  // Commits past the tag, from `git describe` (v1.15.0-3-gabc1234).
  ahead: number;
}

const PRE_RANK: Record<string, number> = { alpha: 0, beta: 1, rc: 2 };

export function parseVersion(v: string): ParsedVersion | null {
  const m = v.trim().match(/^v?(\d+)\.(\d+)\.(\d+)(?:-(alpha|beta|rc)\.(\d+))?(?:-(\d+)-g[0-9a-f]+)?$/);
  if (!m) return null;
  return {
    nums: [Number(m[1]), Number(m[2]), Number(m[3])],
    pre: m[4] ? [PRE_RANK[m[4]], Number(m[5])] : null,
    ahead: m[6] ? Number(m[6]) : 0,
  };
}

/** Negative when a < b, positive when a > b, 0 when equal. */
export function compareVersions(a: ParsedVersion, b: ParsedVersion): number {
  for (let i = 0; i < 3; i++) {
    if (a.nums[i] !== b.nums[i]) return a.nums[i] - b.nums[i];
  }
  if (a.pre === null || b.pre === null) {
    if (a.pre !== b.pre) return a.pre === null ? 1 : -1;
  } else if (a.pre[0] !== b.pre[0]) {
    return a.pre[0] - b.pre[0];
  } else if (a.pre[1] !== b.pre[1]) {
    return a.pre[1] - b.pre[1];
  }
  return a.ahead - b.ahead;
}

export function firmwareSync(versions: FirmwareVersions): FirmwareSync {
  if (versions.device === null) return 'unmanaged';
  if (versions.device === versions.bundled) return 'match';
  const device = parseVersion(versions.device);
  const bundled = parseVersion(versions.bundled);
  if (!device || !bundled) return 'unknown';
  const c = compareVersions(device, bundled);
  return c < 0 ? 'older' : c > 0 ? 'newer' : 'match';
}

/** Whether the main screen should show the out-of-sync notice. */
export function needsFirmwareNotice(sync: FirmwareSync): boolean {
  return sync === 'older' || sync === 'unmanaged';
}
