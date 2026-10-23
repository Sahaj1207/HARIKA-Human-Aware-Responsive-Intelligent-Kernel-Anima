import React, { useCallback, useEffect, useState } from 'react';
import { Check, ExternalLink, Laptop, Zap } from 'lucide-react';
import { env } from '@/config/env';
import { Button, IconTile } from '@/components/apple/controls';
import { errorDetail, llmSettingsService, LocalModelStatus, type LLMSettings } from '@/services/api/llmSettings';

interface BrainSetupProps {
  onDone: () => void;
}

interface Download {
  percent: number | null;
  status: string;
  error?: string;
}

const fieldClass = 'w-full rounded-lg bg-fill px-3 py-2 t-callout text-label outline-none focus:ring-2 focus:ring-accent/50';

/** Which cloud service, if any, already answers for HARIKA. */
function cloudInUse(settings: LLMSettings | null): string | null {
  if (!settings) return null;
  const role = settings.roles.conversation;
  if (role.on_device) return null;
  return settings.services.find((s) => s.id === role.service)?.name ?? role.service;
}

/**
 * First-run choice of how HARIKA thinks. Groq is recommended: free, and about a
 * second per answer. Pasting its key here connects it and picks the right models
 * for understanding and for conversation. A model on this computer is the private,
 * offline alternative.
 */
export const BrainSetup: React.FC<BrainSetupProps> = ({ onDone }) => {
  const [settings, setSettings] = useState<LLMSettings | null>(null);
  const [local, setLocal] = useState<LocalModelStatus | null>(null);
  const [download, setDownload] = useState<Download | null>(null);
  const [key, setKey] = useState('');
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [loaded, status] = await Promise.all([llmSettingsService.get(), llmSettingsService.localStatus()]);
      setSettings(loaded);
      setLocal(status);
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

  const connectGroq = async (e: React.FormEvent) => {
    e.preventDefault();
    setConnecting(true);
    setError(null);
    try {
      const models = await llmSettingsService.connect('groq', key.trim());
      // The fast, accurate pair: a small model to understand requests, a large one to talk.
      await llmSettingsService.choose('understanding', 'groq', models.suggested.understanding);
      setSettings(await llmSettingsService.choose('conversation', 'groq', models.suggested.conversation));
      setKey('');
    } catch (err) {
      setError(errorDetail(err, "That key didn't work. Copy it again from Groq and paste it here."));
    } finally {
      setConnecting(false);
    }
  };

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

  const cloud = cloudInUse(settings);
  const localReady = Boolean(local?.running && local.has_recommended);
  const ready = Boolean(cloud) || localReady;

  let localAction: React.ReactNode;
  if (!local) {
    localAction = <span className="t-footnote text-label-2">Checking…</span>;
  } else if (localReady) {
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
    localAction = <Button kind="tinted" onClick={startDownload}>Download ({local.recommended.size})</Button>;
  } else {
    localAction = (
      <div className="flex flex-col items-end gap-1">
        <Button kind="tinted" onClick={() => void llmSettingsService.openSetupPage('ollama')}>Install Ollama</Button>
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
        <div className="p-4 space-y-3">
          <div className="flex items-center gap-3">
            <IconTile color="var(--orange)"><Zap className="w-4 h-4" strokeWidth={2.25} /></IconTile>
            <div className="flex-1 min-w-0">
              <p className="t-headline">Groq <span className="t-footnote text-accent ml-1">Recommended</span></p>
              <p className="t-footnote text-label-2 mt-0.5">Free, and answers in about a second. Your messages are sent to Groq to answer them.</p>
            </div>
            {cloud && (
              <span className="flex items-center gap-1 t-footnote text-ok">
                <Check className="w-4 h-4" aria-hidden /> {cloud}
              </span>
            )}
          </div>
          {!cloud && (
            <>
              <form className="flex gap-2" onSubmit={connectGroq}>
                <input
                  value={key}
                  onChange={(e) => setKey(e.target.value)}
                  type="password"
                  autoComplete="off"
                  placeholder="Paste your Groq key (gsk_…)"
                  aria-label="Groq API key"
                  className={fieldClass}
                />
                <Button type="submit" disabled={!key.trim() || connecting}>{connecting ? 'Checking…' : 'Connect'}</Button>
              </form>
              <Button kind="plain" className="px-0" onClick={() => void llmSettingsService.openKeyPage('groq')}>
                Get a free key from Groq <ExternalLink className="w-3.5 h-3.5" aria-hidden />
              </Button>
            </>
          )}
        </div>
        <div className="flex items-center gap-3 p-4">
          <IconTile color="var(--green)"><Laptop className="w-4 h-4" strokeWidth={2.25} /></IconTile>
          <div className="flex-1 min-w-0">
            <p className="t-headline">On this computer</p>
            <p className="t-footnote text-label-2 mt-0.5">
              Private and works offline, but slower on most laptops. {local?.running === false ? 'Needs the free Ollama app. ' : ''}
              {local ? `Uses ${local.recommended.model}, which ${local.recommended.reason}.` : ''}
            </p>
            {download?.error && <p className="t-footnote text-danger mt-1">The download stopped: {download.error}</p>}
          </div>
          {localAction}
        </div>
      </div>

      {error && <p className="t-footnote text-danger text-center">{error}</p>}
      <p className="t-caption text-label-2 text-center">Keys are kept in your system's secure keychain. Other services (OpenAI, Anthropic, Gemini, OpenRouter) are in Settings &gt; Brain.</p>

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
