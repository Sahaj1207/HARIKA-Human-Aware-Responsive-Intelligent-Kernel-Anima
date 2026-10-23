import React, { useCallback, useEffect, useState } from 'react';
import { Copy, ExternalLink } from 'lucide-react';
import { env } from '@/config/env';
import { Button, GroupedSection, Row } from '@/components/apple/controls';
import { errorDetail } from '@/services/api/llmSettings';
import { spotifyService, type SpotifyStatus } from '@/services/api/spotify';

const fieldClass = 'w-full rounded-lg bg-fill px-3 py-2 t-callout text-label outline-none focus:ring-2 focus:ring-accent/50';

/** Settings > Accounts > Spotify: register an app once, then connect the account. */
export const SpotifySection: React.FC = () => {
  const [spotify, setSpotify] = useState<SpotifyStatus | null>(null);
  const [clientId, setClientId] = useState('');
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(false);
  const [copied, setCopied] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setSpotify(await spotifyService.status());
    } catch {
      setSpotify(null);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const source = new EventSource(`${env.API_BASE_URL}/events`);
    source.addEventListener('accounts_changed', () => {
      setMessage(null);
      void refresh();
    });
    return () => source.close();
  }, [refresh]);

  const run = async (action: () => Promise<void>, failure: string) => {
    setBusy(true);
    try {
      await action();
    } catch (err) {
      setMessage(errorDetail(err, failure));
    } finally {
      setBusy(false);
    }
  };

  if (!spotify) return null;

  const copyRedirect = async () => {
    try {
      await navigator.clipboard.writeText(spotify.redirect_uri);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setMessage(`Copy this address: ${spotify.redirect_uri}`);
    }
  };

  const footer = spotify.connected
    ? spotify.premium
      ? 'Try "play my liked songs", "what\'s playing?" or "add this to my road trip playlist".'
      : 'Spotify only lets apps start and control playback on Premium accounts; "what\'s playing?" works on any account.'
    : 'Plays your music, liked songs and playlists. Controlling playback needs Spotify Premium.';

  return (
    <GroupedSection title="Spotify" footer={footer}>
      {!spotify.configured || editing ? (
        <div className="px-4 py-3 space-y-3">
          <p className="t-footnote text-label-2">Spotify asks every app to be registered. It's free and takes about five minutes, once:</p>
          <ol className="list-decimal pl-5 space-y-1 t-footnote text-label">
            <li>On Spotify's developer dashboard, sign in and choose Create app (any name, like HARIKA).</li>
            <li>
              For Redirect URI, add this address exactly:{' '}
              <button type="button" onClick={() => void copyRedirect()} className="inline-flex items-center gap-1 text-accent">
                <span className="font-mono t-caption break-all">{spotify.redirect_uri}</span>
                <Copy className="w-3 h-3 shrink-0" aria-hidden />
                <span className="sr-only">Copy</span>
              </button>
              {copied && <span className="t-caption text-ok"> Copied</span>}
            </li>
            <li>Tick Web API, save, then copy the app's Client ID and paste it below.</li>
            <li>Under User Management, add the email of the Spotify account that will use HARIKA.</li>
          </ol>
          <Button kind="plain" className="px-0" onClick={() => void spotifyService.openSetupPage()}>
            Open Spotify's developer dashboard <ExternalLink className="w-3.5 h-3.5" aria-hidden />
          </Button>
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              void run(async () => {
                setSpotify(await spotifyService.setClient(clientId));
                setEditing(false);
                setMessage(null);
              }, "Couldn't save the Client ID.");
            }}
          >
            <input
              value={clientId}
              onChange={(e) => setClientId(e.target.value)}
              placeholder="Client ID"
              aria-label="Spotify Client ID"
              className={fieldClass}
              autoComplete="off"
            />
            <Button type="submit" disabled={!clientId.trim() || busy}>
              Save
            </Button>
          </form>
          {message && <p className="t-footnote text-danger">{message}</p>}
        </div>
      ) : spotify.connected ? (
        <>
          <Row title="Signed in" value={spotify.name} />
          <Row title="Account" value={spotify.premium ? 'Premium' : 'Free'} />
          <Row
            title="Disconnect"
            destructive
            onClick={busy ? undefined : () => void run(async () => setSpotify(await spotifyService.disconnect()), "Couldn't disconnect.")}
          />
        </>
      ) : (
        <div className="px-4 py-3 space-y-2">
          <Button
            className="w-full"
            disabled={busy}
            onClick={() =>
              void run(async () => {
                await spotifyService.signIn();
                setMessage('Finish signing in in your browser, then come back here.');
              }, "Couldn't start signing in.")
            }
          >
            Connect Spotify
          </Button>
          {message && <p className="t-footnote text-label-2">{message}</p>}
          <Row title="Change Client ID" chevron onClick={() => setEditing(true)} />
        </div>
      )}
    </GroupedSection>
  );
};
