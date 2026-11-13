import { useEffect, useState } from 'react';

/** How HARIKA's orb looks (Settings > General > Appearance). Kept in this computer's app storage, which
 * all of HARIKA's windows share, so the main window, the floating orb and notifications match. */
export type OrbStyle = 'starlotus' | 'constellation';

export interface OrbLook {
  style: OrbStyle;
  colours: 'saffron' | 'aurora' | 'royal' | 'moonlight';
  followMood: boolean;
}

const KEY = 'harika_orb_look';
const CHANGED = 'harika:orb-look';
export const DEFAULT_LOOK: OrbLook = { style: 'starlotus', colours: 'saffron', followMood: true };

export function loadLook(): OrbLook {
  try {
    return { ...DEFAULT_LOOK, ...JSON.parse(localStorage.getItem(KEY) || '{}') };
  } catch {
    return DEFAULT_LOOK;
  }
}

export function saveLook(change: Partial<OrbLook>): OrbLook {
  const next = { ...loadLook(), ...change };
  try {
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    // storage unavailable: the change still applies to this window
  }
  window.dispatchEvent(new CustomEvent(CHANGED, { detail: next }));
  return next;
}

/** The current look, updated when it changes here or in another HARIKA window. */
export function useOrbLook(): OrbLook {
  const [look, setLook] = useState<OrbLook>(loadLook);
  useEffect(() => {
    const here = (event: Event) => setLook((event as CustomEvent<OrbLook>).detail);
    const elsewhere = (event: StorageEvent) => {
      if (event.key === KEY) setLook(loadLook());
    };
    window.addEventListener(CHANGED, here);
    window.addEventListener('storage', elsewhere);
    return () => {
      window.removeEventListener(CHANGED, here);
      window.removeEventListener('storage', elsewhere);
    };
  }, []);
  return look;
}
