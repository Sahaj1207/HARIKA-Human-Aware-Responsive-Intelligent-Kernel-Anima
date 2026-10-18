import React, { useEffect, useState } from 'react';
import {
  checkForUpdate, installUpdate, isDesktopApp, progressText,
  type UpdateInfo, type UpdateProgress,
} from '@/services/updates';

/** A quiet check a few seconds after start; if a new version exists, one small banner offers it. */
export const UpdateBanner: React.FC = () => {
  const [update, setUpdate] = useState<UpdateInfo | null>(null);
  const [installing, setInstalling] = useState(false);
  const [progress, setProgress] = useState<UpdateProgress | null>(null);
  const [failed, setFailed] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (!isDesktopApp) return;
    const timer = setTimeout(() => {
      checkForUpdate().then(setUpdate).catch(() => undefined); // offline: checked again next start
    }, 8000);
    return () => clearTimeout(timer);
  }, []);

  if (!update || dismissed) return null;

  const install = async () => {
    setInstalling(true);
    setFailed(false);
    try {
      await installUpdate(setProgress);
    } catch {
      setInstalling(false);
      setFailed(true);
    }
  };

  const message = installing
    ? progressText(progress)
    : failed
      ? "The update didn't install. Try again from Settings."
      : `HARIKA ${update.version} is ready.`;

  return (
    <div role="status" className="mx-auto mt-2 flex items-center gap-3 glass rounded-full px-4 py-1.5 t-footnote text-label">
      <span>{message}</span>
      {!installing && (
        <>
          <button type="button" onClick={() => void install()} className="text-accent font-medium hover:opacity-80">
            Install and restart
          </button>
          <button type="button" onClick={() => setDismissed(true)} className="text-label-2 hover:opacity-80">
            Later
          </button>
        </>
      )}
    </div>
  );
};
