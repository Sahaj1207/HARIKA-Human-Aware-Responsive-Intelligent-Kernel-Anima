import React, { useEffect, useState } from 'react';
import { CalendarDays, Check, MapPin, Mic, Sunrise } from 'lucide-react';
import { env } from '@/config/env';
import { Button, IconTile, Toggle } from '@/components/apple/controls';
import { accountsService, type GoogleStatus } from '@/services/api/accounts';
import { dailyService, type DailySettings } from '@/services/api/daily';
import { speechService, type SpeechStatus } from '@/services/api/speech';

export interface ExtrasState {
  google: boolean;
}

const fieldClass = 'w-44 rounded-lg bg-fill px-3 py-1.5 t-callout text-label outline-none focus:ring-2 focus:ring-accent/50';

/** Optional extras on first run: weather city, morning briefing, Google, and the voice. */
export const ExtrasSetup: React.FC<{ onDone: (state: ExtrasState) => void }> = ({ onDone }) => {
  const [daily, setDaily] = useState<DailySettings | null>(null);
  const [home, setHome] = useState('');
  const [google, setGoogle] = useState<GoogleStatus | null>(null);
  const [speech, setSpeech] = useState<SpeechStatus | null>(null);
  const [voiceProgress, setVoiceProgress] = useState<number | null>(null);

  useEffect(() => {
    dailyService.get().then((d) => { setDaily(d); setHome(d.home); }).catch(() => undefined);
    accountsService.status().then(setGoogle).catch(() => undefined);
    speechService.status().then(setSpeech).catch(() => undefined);
    const source = new EventSource(`${env.API_BASE_URL}/events`);
    source.addEventListener('accounts_changed', () => void accountsService.status().then(setGoogle));
    source.addEventListener('voice_models', (raw) => {
      const update = JSON.parse((raw as MessageEvent).data);
      if (update.status === 'done') {
        setVoiceProgress(null);
        void speechService.status().then(setSpeech);
      } else if (typeof update.percent === 'number') {
        setVoiceProgress(update.percent);
      }
    });
    return () => source.close();
  }, []);

  const saveHome = async () => {
    if (daily && home.trim() !== daily.home) setDaily(await dailyService.update({ home: home.trim() }));
  };

  const finish = async () => {
    await saveHome().catch(() => undefined);
    onDone({ google: Boolean(google?.connected) });
  };

  const voiceAction = !speech ? null : speech.ready ? (
    <Toggle
      label="Listen for Hey HARIKA"
      checked={speech.settings.wake_word}
      onChange={async (on) => setSpeech(await speechService.update({ wake_word: on }))}
    />
  ) : voiceProgress !== null || speech.downloading ? (
    <span className="t-footnote text-label-2">Downloading{voiceProgress !== null ? ` ${voiceProgress}%` : '…'}</span>
  ) : (
    <Button kind="tinted" onClick={async () => setSpeech(await speechService.downloadModels())}>
      Download ({Math.round(speech.missing_mb)} MB)
    </Button>
  );

  return (
    <div className="w-full max-w-xl space-y-6 bubble-enter">
      <div className="text-center space-y-2">
        <h1 className="t-large-title text-label">A few extras</h1>
        <p className="t-body text-label-2">All optional. Each one is also in Settings.</p>
      </div>

      <div className="rounded-2xl bg-surface dark:bg-surface-2 divide-y divide-separator overflow-hidden text-left">
        <div className="flex items-center gap-3 p-4">
          <IconTile color="var(--blue)"><MapPin className="w-4 h-4" strokeWidth={2.25} /></IconTile>
          <div className="flex-1 min-w-0">
            <p className="t-headline">Your city</p>
            <p className="t-footnote text-label-2 mt-0.5">For the weather. Leave empty to use your approximate location.</p>
          </div>
          <input value={home} onChange={(e) => setHome(e.target.value)} onBlur={() => void saveHome()}
            placeholder="e.g. Hyderabad" aria-label="Your city" className={fieldClass} />
        </div>

        <div className="flex items-center gap-3 p-4">
          <IconTile color="var(--orange)"><Sunrise className="w-4 h-4" strokeWidth={2.25} /></IconTile>
          <div className="flex-1 min-w-0">
            <p className="t-headline">Morning briefing</p>
            <p className="t-footnote text-label-2 mt-0.5">Weather, your day and the headlines at {daily?.briefing_time ?? '08:00'}.</p>
          </div>
          {daily && (
            <Toggle label="Morning briefing" checked={daily.briefing_enabled}
              onChange={async (on) => setDaily(await dailyService.update({ briefing_enabled: on }))} />
          )}
        </div>

        {google?.configured && (
          <div className="flex items-center gap-3 p-4">
            <IconTile color="var(--red)"><CalendarDays className="w-4 h-4" strokeWidth={2.25} /></IconTile>
            <div className="flex-1 min-w-0">
              <p className="t-headline">Calendar and email</p>
              <p className="t-footnote text-label-2 mt-0.5">
                {google.connected ? `Connected as ${google.email}.` : 'Google Calendar and Gmail. Emails are only sent when you say yes.'}
              </p>
            </div>
            {google.connected ? (
              <span className="flex items-center gap-1 t-footnote text-ok"><Check className="w-4 h-4" aria-hidden /> Connected</span>
            ) : (
              <Button kind="tinted" onClick={() => void accountsService.signInWithGoogle()}>Sign in with Google</Button>
            )}
          </div>
        )}

        <div className="flex items-center gap-3 p-4">
          <IconTile color="var(--pink)"><Mic className="w-4 h-4" strokeWidth={2.25} /></IconTile>
          <div className="flex-1 min-w-0">
            <p className="t-headline">Talk to HARIKA</p>
            <p className="t-footnote text-label-2 mt-0.5">
              {speech?.ready ? 'Say “Hey HARIKA” from anywhere. It works offline.' : 'Download the offline voice to talk and hear replies.'}
            </p>
          </div>
          {voiceAction}
        </div>
      </div>

      <div className="flex justify-center">
        <Button onClick={() => void finish()} className="px-8 py-2.5">Continue</Button>
      </div>
    </div>
  );
};
