/** In-app updates through HARIKA's desktop shell (check, download, install, restart). */

export const isDesktopApp = typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;

export interface UpdateInfo {
  version: string;
  current: string;
  notes?: string | null;
}

export interface UpdateProgress {
  downloaded: number;
  total?: number | null;
}

export async function appVersion(): Promise<string | null> {
  if (!isDesktopApp) return null;
  const { getVersion } = await import('@tauri-apps/api/app');
  return getVersion();
}

/** A newer version, or null when HARIKA is up to date. Throws if the update server can't be reached. */
export async function checkForUpdate(): Promise<UpdateInfo | null> {
  if (!isDesktopApp) return null;
  const { invoke } = await import('@tauri-apps/api/core');
  return invoke<UpdateInfo | null>('check_update');
}

/** Downloads (signature-checked), installs and restarts HARIKA. */
export async function installUpdate(onProgress?: (progress: UpdateProgress) => void): Promise<void> {
  const { invoke } = await import('@tauri-apps/api/core');
  const { listen } = await import('@tauri-apps/api/event');
  const stop = await listen<UpdateProgress>('update-progress', (event) => onProgress?.(event.payload));
  try {
    await invoke('install_update');
  } finally {
    stop();
  }
}

export function progressText(progress: UpdateProgress | null): string {
  if (!progress) return 'Downloading…';
  const mb = (bytes: number) => (bytes / 1024 / 1024).toFixed(1);
  return progress.total
    ? `Downloading… ${Math.round((progress.downloaded / progress.total) * 100)}%`
    : `Downloading… ${mb(progress.downloaded)} MB`;
}
