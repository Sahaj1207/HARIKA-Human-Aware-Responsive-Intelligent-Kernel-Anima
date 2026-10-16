import React, { useCallback, useEffect, useState } from 'react';
import { Check, Cloud, Laptop } from 'lucide-react';
import { env } from '@/config/env';
import { Button, IconTile } from '@/components/apple/controls';
import { errorDetail, llmSettingsService, LocalModelStatus } from '@/services/api/llmSettings';

interface BrainSetupProps {
  onDone: () => void;
  onUseCloud: () => void;
}

interface Download {
  percent: number | null;
  status: string;
  error?: string;
}

/**
 * First-run choice of where HARIKA thinks. A new computer usually has no
 * model yet: install Ollama and download one sized for this machine, or
 * connect a cloud service instead.
 */
export const BrainSetup: React.FC<BrainSetupProps> = ({ onDone, onUseCloud }) => {
  const [local, setLocal] = useState<LocalModelStatus | null>(null);
  const [download, setDownload] = useState<Download | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setLocal(await llmSettingsService.localStatus());
    } catch (err) {
      setError(errorDetail(err, "HARIKA's engine is still starting. Try again in a moment."));
    }
  }, []);

  useEffect(() => {
    void refresh();
    const source = new EventSource(`${env.API_BASE_URL}/events`);
    source.addEventListener('model_download', (raw) => {
      const update = JSON.parse((raw as MessageEvent).data);
      if (update.status === 'done') {
        setDownload(null);
        void refresh();
      } else if (update.status === 'failed') {
        setDownload({ percent: null, status: 'failed', error: update.error });
      } else {
        setDownload((prev) => ({ percent: update.percent ?? prev?.percent ?? null, status: update.status }));
      }
    });
    return () => source.close();
  }, [refresh]);

  const startDownload = async () => {
    if (!local) return;
    setError(null);
    setDownload({ percent: null, status: 'starting' });
    try {
      await llmSettingsService.downloadLocalModel(local.recommended.model);
    } catch (err) {
      setDownload(null);
      setError(errorDetail(err, "Couldn't start the download."));
    }
  };

  const ready = Boolean(local?.running && local.has_recommended);

  let localAction: React.ReactNode;
  if (!local) {
    localAction = <span className="t-footnote text-label-2">Checking…</span>;
  } else if (ready) {
    localAction = (
      <span className="flex items-center gap-1 t-footnote text-ok">
        <Check className="w-4 h-4" aria-hidden /> Ready
      </span>
    );
  } else if (download && !download.error) {
    localAction = (
      <div className="w-40 space-y-1" aria-live="polite">
        <div className="h-1.5 rounded-full bg-fill overflow-hidden">
          <div className="h-full bg-accent transition-[width] duration-300" style={{ width: `${download.percent ?? 2}%` }} />
        </div>
        <p className="t-caption text-label-2 text-right">
          {download.percent !== null ? `Downloading ${download.percent}%` : 'Preparing…'}
        </p>
      </div>
    );
  } else if (local.running) {
    localAction = <Button onClick={startDownload}>Download ({local.recommended.size})</Button>;
  } else {
    localAction = (
      <div className="flex flex-col items-end gap-1">
        <Button onClick={() => void llmSettingsService.openSetupPage('ollama')}>Install Ollama</Button>
        <Button kind="plain" className="px-0" onClick={() => void refresh()}>I've installed it</Button>
      </div>
    );
  }

  return (
    <div className="w-full max-w-xl space-y-6 bubble-enter">
      <div className="text-center space-y-2">
        <h1 className="t-large-title text-label">How should HARIKA think?</h1>
        <p className="t-body text-label-2">You can change this any time in Settings.</p>
      </div>

      <div className="rounded-2xl bg-surface dark:bg-surface-2 divide-y divide-separator overflow-hidden text-left">
        <div className="flex items-center gap-3 p-4">
          <IconTile color="var(--green)"><Laptop className="w-4 h-4" strokeWidth={2.25} /></IconTile>
          <div className="flex-1 min-w-0">
            <p className="t-headline">On this computer</p>
            <p className="t-footnote text-label-2 mt-0.5">
              Private and free. {local?.running === false ? 'Needs the free Ollama app. ' : ''}
              {local ? `Uses ${local.recommended.model}, which ${local.recommended.reason}.` : ''}
            </p>
            {download?.error && <p className="t-footnote text-danger mt-1">The download stopped: {download.error}</p>}
          </div>
          {localAction}
        </div>
        <div className="flex items-center gap-3 p-4">
          <IconTile color="var(--blue)"><Cloud className="w-4 h-4" strokeWidth={2.25} /></IconTile>
          <div className="flex-1 min-w-0">
            <p className="t-headline">With a cloud service</p>
            <p className="t-footnote text-label-2 mt-0.5">
              Faster on most computers. Sign in with OpenRouter, or use a key from OpenAI, Anthropic, Google or Groq.
            </p>
          </div>
          <Button kind="tinted" onClick={onUseCloud}>Set up</Button>
        </div>
      </div>

      {error && <p className="t-footnote text-danger text-center">{error}</p>}

      <div className="flex justify-center">
        {ready ? (
          <Button onClick={onDone} className="px-8 py-2.5">Continue</Button>
        ) : (
          <Button kind="plain" onClick={onDone}>Skip for now</Button>
        )}
      </div>
    </div>
  );
};
