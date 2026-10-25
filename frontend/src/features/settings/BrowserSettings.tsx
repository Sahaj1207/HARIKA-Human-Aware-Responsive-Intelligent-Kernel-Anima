import React, { useEffect, useState } from 'react';
import { Button, GroupedSection, Row } from '@/components/apple/controls';
import { browserService, type ExtensionStatus } from '@/services/api/browser';

/** Settings > Privacy: where website tasks run, and connecting HARIKA's extension. */
export const BrowserSection: React.FC = () => {
  const [status, setStatus] = useState<ExtensionStatus | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    const load = () =>
      browserService
        .status()
        .then((s) => alive && (setStatus(s), setError(null)))
        .catch(() => alive && setError("HARIKA's engine isn't running, so this can't be shown."));
    void load();
    const timer = setInterval(load, 3000); // shows "Connected" as soon as the extension pairs
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, []);

  const act = async (change: () => Promise<ExtensionStatus>) => {
    try {
      setStatus(await change());
    } catch {
      setError("Couldn't do that. Try again.");
    }
  };

  const copy = async () => {
    if (!status) return;
    await navigator.clipboard.writeText(status.code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!status) {
    return error ? (
      <GroupedSection title="Your browser">
        <Row title={error} />
      </GroupedSection>
    ) : null;
  }

  return (
    <GroupedSection
      title="Your browser"
      footer="Website tasks run in one tab HARIKA opens, grouped as “HARIKA”. She never looks at your other tabs, never types passwords or card numbers, and asks before anything final."
    >
      <Row
        title="Website tasks run in"
        subtitle={
          status.connected
            ? `Your ${status.browser}, through HARIKA's extension.`
            : "HARIKA's own browser window. Add the extension to use your Chrome or Edge, with your sign-ins."
        }
      />
      {!status.connected && (
        <Row
          title="Add the extension"
          subtitle="In Chrome or Edge, open the Extensions page, turn on Developer mode, choose Load unpacked and pick the folder this opens. Then paste the pairing code into the extension."
          accessory={<Button kind="tinted" onClick={() => void act(browserService.openFolder)}>Open folder</Button>}
        />
      )}
      <Row
        title="Pairing code"
        subtitle={<span className="font-mono tracking-wide select-all">{status.code}</span>}
        accessory={
          <div className="flex gap-2">
            <Button kind="tinted" onClick={() => void copy()}>{copied ? 'Copied' : 'Copy'}</Button>
            <Button kind="plain" onClick={() => void act(browserService.newCode)}>New code</Button>
          </div>
        }
      />
      {error && <Row title={error} />}
    </GroupedSection>
  );
};
