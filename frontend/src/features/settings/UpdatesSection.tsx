import React, { useEffect, useState } from 'react';
import { Button, GroupedSection, Row } from '@/components/apple/controls';
import {
  appVersion, checkForUpdate, installUpdate, isDesktopApp, progressText,
  type UpdateInfo, type UpdateProgress,
} from '@/services/updates';

type State = 'idle' | 'checking' | 'current' | 'available' | 'installing' | 'error';

/** Settings > General: HARIKA's version, checking for updates, and installing one. */
export const UpdatesSection: React.FC = () => {
  const [version, setVersion] = useState<string | null>(null);
  const [state, setState] = useState<State>('idle');
  const [update, setUpdate] = useState<UpdateInfo | null>(null);
  const [progress, setProgress] = useState<UpdateProgress | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    appVersion().then(setVersion).catch(() => setVersion(null));
  }, []);

  if (!isDesktopApp) return null;

  const check = async () => {
    setState('checking');
    setError(null);
    try {
      const found = await checkForUpdate();
      setUpdate(found);
      setState(found ? 'available' : 'current');
    } catch {
      setState('error');
      setError("Couldn't reach the update server. Check your internet connection and try again.");
    }
  };

  const install = async () => {
    setState('installing');
    try {
      await installUpdate(setProgress); // HARIKA restarts when this succeeds
    } catch (err) {
      setState('error');
      setError(`The update didn't install: ${String(err)}`);
    }
  };

  const status: Record<State, string> = {
    idle: '',
    checking: 'Checking…',
    current: "You're up to date.",
    available: `HARIKA ${update?.version ?? ''} is available.`,
    installing: progressText(progress),
    error: error ?? '',
  };

  return (
    <GroupedSection
      title="Updates"
      footer={update?.notes && state === 'available' ? update.notes : 'Updates are signed, so HARIKA only installs genuine ones.'}
    >
      <Row title="HARIKA" value={version ? `Version ${version}` : undefined} />
      <Row
        title={status[state] || 'Check for a newer version'}
        accessory={
          state === 'available' ? (
            <Button onClick={() => void install()}>Install and restart</Button>
          ) : (
            <Button kind="tinted" disabled={state === 'checking' || state === 'installing'} onClick={() => void check()}>
              Check for updates
            </Button>
          )
        }
      />
    </GroupedSection>
  );
};
