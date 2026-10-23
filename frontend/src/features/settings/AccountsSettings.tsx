import React, { useCallback, useEffect, useState } from 'react';
import { ExternalLink } from 'lucide-react';
import { env } from '@/config/env';
import { Button, GroupedSection, Row } from '@/components/apple/controls';
import { accountsService, openGoogleSetupPage, type GoogleStatus } from '@/services/api/accounts';
import { errorDetail } from '@/services/api/llmSettings';
import { SpotifySection } from './SpotifySettings';

const fieldClass = 'w-full rounded-lg bg-fill px-3 py-2 t-callout text-label outline-none focus:ring-2 focus:ring-accent/50';

const SETUP_STEPS = [
  'In Google Cloud Console, create a project (any name, like HARIKA).',
  'Under APIs & Services, enable the Google Calendar API and the Gmail API.',
  'Under Google Auth Platform, set up the app: External audience, name HARIKA, and add the Gmail address that will sign in as a test user.',
  'Under Clients, create a client of type Desktop app, then paste its Client ID and Client secret below.',
  'Under Audience, choose Publish app. Otherwise Google signs HARIKA out every 7 days. Sign-in will say Google hasn\'t verified the app: choose Advanced, then Go to HARIKA.',
];

/** Paste the user's own Google OAuth client (one time per computer). */
const GoogleClientForm: React.FC<{ onSaved: (status: GoogleStatus) => void }> = ({ onSaved }) => {
  const [clientId, setClientId] = useState('');
  const [secret, setSecret] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      onSaved(await accountsService.setGoogleClient(clientId, secret));
      setError(null);
    } catch (err) {
      setError(errorDetail(err, "Couldn't save the client. Check both values and try again."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="px-4 py-3 space-y-3">
      <p className="t-footnote text-label-2">
        Google asks every app that reads email to be registered. It's free and takes about ten minutes, once:
      </p>
      <ol className="list-decimal pl-5 space-y-1 t-footnote text-label">
        {SETUP_STEPS.map((step) => (
          <li key={step}>{step}</li>
        ))}
      </ol>
      <Button kind="plain" className="px-0" onClick={() => void openGoogleSetupPage()}>
        Open Google Cloud Console <ExternalLink className="w-3.5 h-3.5" aria-hidden />
      </Button>
      <form className="space-y-2" onSubmit={save}>
        <input
          value={clientId}
          onChange={(e) => setClientId(e.target.value)}
          placeholder="Client ID (…apps.googleusercontent.com)"
          aria-label="Google OAuth client ID"
          className={fieldClass}
          autoComplete="off"
        />
        <input
          value={secret}
          onChange={(e) => setSecret(e.target.value)}
          placeholder="Client secret"
          aria-label="Google OAuth client secret"
          type="password"
          className={fieldClass}
          autoComplete="off"
        />
        <div className="flex items-center justify-between">
          <span className="t-caption text-label-2">The secret is kept in your system's secure keychain</span>
          <Button type="submit" disabled={!clientId.trim() || !secret.trim() || busy}>
            {busy ? 'Saving…' : 'Save'}
          </Button>
        </div>
      </form>
      {error && <p className="t-footnote text-danger">{error}</p>}
    </div>
  );
};

export const AccountsSettings: React.FC = () => {
  const [google, setGoogle] = useState<GoogleStatus | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [showOwnClient, setShowOwnClient] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setGoogle(await accountsService.status());
      setLoadError(null);
    } catch (err) {
      setLoadError(errorDetail(err, "HARIKA's engine isn't running, so accounts can't be shown."));
    }
  }, []);

  useEffect(() => {
    void refresh();
    // Sign-in finishes in the browser; the backend announces it here.
    const source = new EventSource(`${env.API_BASE_URL}/events`);
    source.addEventListener('accounts_changed', () => {
      setMessage(null);
      void refresh();
    });
    return () => source.close();
  }, [refresh]);

  const signIn = async () => {
    setBusy(true);
    try {
      await accountsService.signInWithGoogle();
      setMessage('Finish signing in in your browser, then come back here.');
    } catch (err) {
      setMessage(errorDetail(err, "Couldn't start signing in."));
    } finally {
      setBusy(false);
    }
  };

  const disconnect = async () => {
    setBusy(true);
    try {
      setGoogle(await accountsService.disconnectGoogle());
      setMessage(null);
    } finally {
      setBusy(false);
    }
  };

  if (loadError) {
    return (
      <GroupedSection>
        <Row title={loadError} />
      </GroupedSection>
    );
  }
  if (!google) return null;

  const missing = google.connected
    ? [!google.calendar && 'your calendar', !google.email_read && 'reading email', !google.email_send && 'sending email'].filter(Boolean)
    : [];

  return (
    <div className="space-y-7">
      <GroupedSection
        title="Google"
        footer={
          google.connected
            ? missing.length
              ? `Google didn't allow ${missing.join(' and ')}. Sign in again and tick every box to use it.`
              : 'Try "what\'s on my calendar today?" or "any new emails?". Emails are only sent after you say yes.'
            : 'Calendar and Gmail. HARIKA only acts when you ask, and never sends an email without your yes.'
        }
      >
        {!google.configured || showOwnClient ? (
          <GoogleClientForm
            onSaved={(status) => {
              setShowOwnClient(false);
              setGoogle(status);
            }}
          />
        ) : google.connected ? (
          <>
            <Row title="Signed in" value={google.email} />
            <Row
              title="Calendar and email"
              value={missing.length ? 'Partly allowed' : 'Connected'}
            />
            <Row title="Disconnect" destructive onClick={busy ? undefined : () => void disconnect()} />
          </>
        ) : (
          <div className="px-4 py-3 space-y-2">
            <Button onClick={() => void signIn()} disabled={busy} className="w-full">
              Sign in with Google
            </Button>
            {message && <p className="t-footnote text-label-2">{message}</p>}
          </div>
        )}
      </GroupedSection>
      {google.configured && !google.connected && !showOwnClient && (
        <GroupedSection
          title="Advanced"
          footer={
            google.own_client
              ? 'HARIKA is using your own Google OAuth client.'
              : "For developers: sign in through your own Google Cloud OAuth client instead of HARIKA's."
          }
        >
          <Row title={google.own_client ? 'Change your Google client' : 'Use your own Google client'} chevron onClick={() => setShowOwnClient(true)} />
          {google.own_client && google.built_in_client && (
            <Row
              title="Use HARIKA's built-in client"
              onClick={busy ? undefined : () => void accountsService.useBuiltInGoogleClient().then(setGoogle)}
            />
          )}
        </GroupedSection>
      )}
      <SpotifySection />
    </div>
  );
};
