import React, { useCallback, useEffect, useState } from 'react';
import { Play } from 'lucide-react';
import { env } from '@/config/env';
import { Button, GroupedSection, Row, Segmented, Toggle } from '@/components/apple/controls';
import { errorDetail } from '@/services/api/llmSettings';
import { SpeakReplies, speechService, SpeechStatus } from '@/services/api/speech';

const isMac = typeof navigator !== 'undefined' && /Mac/i.test(navigator.platform);

/** Settings > Voice: download the offline voice, "Hey HARIKA", and how HARIKA speaks. */
export const VoiceSettings: React.FC = () => {
  const [status, setStatus] = useState<SpeechStatus | null>(null);
  const [progress, setProgress] = useState<{ percent: number | null; status: string; error?: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setStatus(await speechService.status());
      setError(null);
    } catch (err) {
      setError(errorDetail(err, "HARIKA's engine isn't running, so voice settings can't be shown."));
    }
  }, []);

  useEffect(() => {
    void refresh();
    const source = new EventSource(`${env.API_BASE_URL}/events`);
    source.addEventListener('voice_models', (raw) => {
      const update = JSON.parse((raw as MessageEvent).data);
      if (update.status === 'done') {
        setProgress(null);
        void refresh();
      } else {
        setProgress({ percent: update.percent ?? null, status: update.status, error: update.error });
      }
    });
    return () => source.close();
  }, [refresh]);

  const change = async (changes: Parameters<typeof speechService.update>[0]) => {
    try {
      setStatus(await speechService.update(changes));
    } catch (err) {
      setError(errorDetail(err, "Couldn't save that."));
    }
  };

  if (error) return <p className="t-callout text-label-2">{error}</p>;
  if (!status) return <p className="t-callout text-label-2">Loading…</p>;
  const { settings } = status;

  return (
    <div className="space-y-7">
      {!status.ready && (
        <GroupedSection
          title="Download"
          footer="Speech recognition and HARIKA's voice run on this computer, so nothing you say leaves it."
        >
          <Row
            title="HARIKA's voice"
            subtitle={
              progress?.error
                ? `The download stopped: ${progress.error}`
                : progress
                ? `${progress.status}${progress.percent !== null ? ` (${progress.percent}%)` : ''}`
                : `About ${Math.round(status.missing_mb)} MB, downloaded once.`
            }
            accessory={
              progress && !progress.error ? (
                <div className="w-32 h-1.5 rounded-full bg-fill overflow-hidden" aria-hidden>
                  <div className="h-full bg-accent transition-[width] duration-300" style={{ width: `${progress.percent ?? 2}%` }} />
                </div>
              ) : (
                <Button
                  onClick={async () => {
                    setProgress({ percent: null, status: 'Starting' });
                    try {
                      setStatus(await speechService.downloadModels());
                    } catch (err) {
                      setProgress({ percent: null, status: '', error: errorDetail(err, "couldn't start") });
                    }
                  }}
                >
                  {progress?.error ? 'Try again' : 'Download'}
                </Button>
              )
            }
          />
        </GroupedSection>
      )}

      <GroupedSection
        title="Listening"
        footer={
          <>
            Say “Hey HARIKA” followed by what you need, from anywhere. Listening happens entirely on this computer:
            speech is recognised in memory and ignored unless it starts with “Hey HARIKA”, and nothing is recorded.
            You can also press {isMac ? '⌃⇧Space' : 'Ctrl + Shift + Space'} and tap the microphone.
          </>
        }
      >
        <Row
          title="Listen for “Hey HARIKA”"
          subtitle={status.state === 'off' ? undefined : status.state === 'idle' ? 'Listening' : `Now ${status.state}`}
          accessory={
            <Toggle
              label="Listen for Hey HARIKA"
              checked={settings.wake_word}
              disabled={!status.ready}
              onChange={(on) => void change({ wake_word: on })}
            />
          }
        />
      </GroupedSection>

      <GroupedSection title="Speaking">
        <Row
          title="Speak replies"
          accessory={
            <Segmented<SpeakReplies>
              label="Speak replies"
              value={settings.speak_replies}
              onChange={(value) => void change({ speak_replies: value })}
              options={[
                { value: 'voice', label: 'When I talk' },
                { value: 'always', label: 'Always' },
                { value: 'never', label: 'Never' },
              ]}
            />
          }
        />
        <Row
          title="Speed"
          accessory={
            <input
              type="range"
              min={0.8}
              max={1.3}
              step={0.05}
              value={settings.speed}
              aria-label="Speaking speed"
              onChange={(e) => void change({ speed: Number(e.target.value) })}
              className="w-40 accent-[var(--blue)]"
            />
          }
        />
      </GroupedSection>

      <AzureSection status={status} onChange={setStatus} />

      <GroupedSection
        title={settings.engine === 'azure' && status.azure.connected ? 'Offline voice' : 'Voice'}
        footer={settings.engine === 'azure' && status.azure.connected ? 'Used when Azure is unreachable.' : undefined}
      >
        {status.voices.map((voice) => (
          <Row
            key={voice.id}
            title={voice.name}
            subtitle={voice.downloaded ? voice.accent : `${voice.accent}, ${Math.round(voice.size_mb)} MB download`}
            accessory={
              <span className="flex items-center gap-2">
                <button
                  type="button"
                  aria-label={`Preview ${voice.name}`}
                  disabled={!voice.downloaded}
                  onClick={() => void speechService.preview(voice.id)}
                  className="w-7 h-7 grid place-items-center rounded-full bg-fill text-accent disabled:opacity-40"
                >
                  <Play className="w-3.5 h-3.5 fill-current" />
                </button>
                {settings.voice === voice.id ? (
                  <span className="t-callout text-accent w-12 text-center" aria-label="Current voice">✓</span>
                ) : (
                  <Button kind="plain" className="w-12" onClick={() => void change({ voice: voice.id })}>Use</Button>
                )}
              </span>
            }
          />
        ))}
      </GroupedSection>
    </div>
  );
};

const fieldClass = 'w-full rounded-lg bg-fill px-3 py-2 t-callout text-label outline-none focus:ring-2 focus:ring-accent/50';

/** Azure AI Speech: neural voices that sound cheerful, gentle or excited to match what HARIKA says. */
const AzureSection: React.FC<{ status: SpeechStatus; onChange: (status: SpeechStatus) => void }> = ({ status, onChange }) => {
  const [key, setKey] = useState('');
  const [region, setRegion] = useState(status.azure.region || '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { settings, azure } = status;

  const connect = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      onChange(await speechService.connectAzure(key, region));
      setKey('');
      setError(null);
    } catch (err) {
      setError(errorDetail(err, "Couldn't connect to Azure."));
    } finally {
      setBusy(false);
    }
  };

  if (!azure.connected) {
    return (
      <GroupedSection
        title="Expressive voice"
        footer="Azure AI Speech voices sound cheerful, gentle or excited to match what HARIKA says. Create a free Speech resource at portal.azure.com, then paste its Key 1 and Region (for example centralindia)."
      >
        <form className="px-4 py-3 space-y-2" onSubmit={connect}>
          <input value={key} onChange={(e) => setKey(e.target.value)} type="password" autoComplete="off"
            placeholder="Key" aria-label="Azure Speech key" className={fieldClass} />
          <div className="flex gap-2">
            <input value={region} onChange={(e) => setRegion(e.target.value)} autoComplete="off"
              placeholder="Region, e.g. centralindia" aria-label="Azure region" className={fieldClass} />
            <Button type="submit" disabled={!key.trim() || !region.trim() || busy}>{busy ? 'Checking…' : 'Connect'}</Button>
          </div>
          {error && <p className="t-footnote text-danger">{error}</p>}
        </form>
      </GroupedSection>
    );
  }

  return (
    <GroupedSection
      title="Expressive voice"
      footer={`Connected to Azure (${azure.region}). The key is kept in your system's secure keychain.`}
    >
      <Row
        title="Use expressive voice"
        accessory={
          <Toggle
            label="Use expressive voice"
            checked={settings.engine === 'azure'}
            onChange={async (on) => onChange(await speechService.update({ engine: on ? 'azure' : 'piper' }))}
          />
        }
      />
      {settings.engine === 'azure' &&
        azure.voices.map((voice) => (
          <Row
            key={voice.id}
            title={voice.name}
            subtitle={voice.accent}
            accessory={
              <span className="flex items-center gap-2">
                <button type="button" aria-label={`Preview ${voice.name}`} onClick={() => void speechService.preview(voice.id)}
                  className="w-7 h-7 grid place-items-center rounded-full bg-fill text-accent">
                  <Play className="w-3.5 h-3.5 fill-current" />
                </button>
                {settings.azure_voice === voice.id ? (
                  <span className="t-callout text-accent w-12 text-center" aria-label="Current voice">✓</span>
                ) : (
                  <Button kind="plain" className="w-12" onClick={async () => onChange(await speechService.update({ azure_voice: voice.id }))}>Use</Button>
                )}
              </span>
            }
          />
        ))}
      <Row title="Disconnect Azure" destructive onClick={async () => onChange(await speechService.disconnectAzure())} />
    </GroupedSection>
  );
};
