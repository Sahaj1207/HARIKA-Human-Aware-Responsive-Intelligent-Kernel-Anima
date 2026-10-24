import React, { useCallback, useEffect, useState } from 'react';
import { Check, ExternalLink } from 'lucide-react';
import { env } from '@/config/env';
import { Button, GroupedSection, Row, Toggle } from '@/components/apple/controls';
import {
  errorDetail, llmSettingsService, LLMService, LLMSettings, Role,
} from '@/services/api/llmSettings';

const ROLE_COPY: Record<Role, { title: string; hint: string }> = {
  understanding: {
    title: 'Understanding requests',
    hint: 'Turns what you say into actions. A small, fast model works best.',
  },
  conversation: {
    title: 'Conversation',
    hint: 'Answers questions and chats with you. A larger model sounds more natural.',
  },
};

const PlaceBadge: React.FC<{ onDevice: boolean }> = ({ onDevice }) => (
  <span className={`t-caption font-medium px-2 py-0.5 rounded-full ${onDevice ? 'bg-ok/15 text-ok' : 'bg-accent/15 text-accent'}`}>
    {onDevice ? 'On this computer' : 'Cloud'}
  </span>
);

const fieldClass = 'w-full rounded-lg bg-fill px-3 py-2 t-callout text-label outline-none focus:ring-2 focus:ring-accent/50';

/** Picks a connected service and one of its models for a role. */
const RoleEditor: React.FC<{
  role: Role;
  settings: LLMSettings;
  onSaved: (next: LLMSettings) => void;
  onCancel: () => void;
}> = ({ role, settings, onSaved, onCancel }) => {
  const connected = settings.services.filter((s) => s.connected);
  const [service, setService] = useState(settings.roles[role].service);
  const [model, setModel] = useState(settings.roles[role].model);
  const [models, setModels] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setModels(null);
    setError(null);
    // Another service's model name means nothing here; wait for this service's own list.
    if (service !== settings.roles[role].service) setModel('');
    llmSettingsService
      .models(service)
      .then((list) => {
        if (cancelled) return;
        setModels(list.models);
        if (service !== settings.roles[role].service || !list.models.includes(model)) setModel(list.suggested[role]);
      })
      .catch((err) => !cancelled && setError(errorDetail(err, "Couldn't load the list of models.")));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [service]);

  const save = async () => {
    try {
      onSaved(await llmSettingsService.choose(role, service, model));
    } catch (err) {
      setError(errorDetail(err, "Couldn't save that choice."));
    }
  };

  return (
    <div className="px-4 py-3 space-y-3 bg-surface-2/50">
      <label className="block space-y-1">
        <span className="t-footnote text-label-2">Service</span>
        <select className={fieldClass} value={service} onChange={(e) => setService(e.target.value)}>
          {connected.map((s) => (
            <option key={s.id} value={s.id}>{s.name}</option>
          ))}
        </select>
      </label>
      <label className="block space-y-1">
        <span className="t-footnote text-label-2">Model</span>
        {models && models.length > 0 ? (
          <select className={fieldClass} value={model} onChange={(e) => setModel(e.target.value)}>
            {!models.includes(model) && model && <option value={model}>{model}</option>}
            {models.map((m) => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
        ) : (
          <input className={fieldClass} value={model} onChange={(e) => setModel(e.target.value)} placeholder={models ? 'Model name' : 'Loading models…'} />
        )}
      </label>
      {error && <p className="t-footnote text-danger">{error}</p>}
      <div className="flex justify-end gap-2">
        <Button kind="plain" onClick={onCancel}>Cancel</Button>
        <Button onClick={save} disabled={!model || models === null}>Use this model</Button>
      </div>
    </div>
  );
};

/** Connect panel for one service: sign in, or paste a key. */
const ServiceConnect: React.FC<{ service: LLMService; onDone: () => void }> = ({ service, onDone }) => {
  const [key, setKey] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ text: string; error: boolean } | null>(null);

  const connect = async () => {
    setBusy(true);
    setMessage(null);
    try {
      await llmSettingsService.connect(service.id, key);
      setKey('');
      onDone();
    } catch (err) {
      setMessage({ text: errorDetail(err, "Couldn't connect with that key."), error: true });
    } finally {
      setBusy(false);
    }
  };

  const signIn = async () => {
    setMessage({ text: 'Finish signing in in your browser. This page updates on its own.', error: false });
    try {
      await llmSettingsService.signInWithOpenRouter();
    } catch (err) {
      setMessage({ text: errorDetail(err, "Couldn't open the sign-in page."), error: true });
    }
  };

  return (
    <div className="px-4 py-3 space-y-3 bg-surface-2/50">
      {service.sign_in && (
        <>
          <Button onClick={signIn} className="w-full">Sign in with {service.name}</Button>
          <p className="t-footnote text-label-2 text-center">or paste an API key</p>
        </>
      )}
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (key.trim()) void connect();
        }}
      >
        <input
          type="password"
          autoComplete="off"
          spellCheck={false}
          value={key}
          onChange={(e) => setKey(e.target.value)}
          placeholder={`${service.name} API key`}
          aria-label={`${service.name} API key`}
          className={`${fieldClass} flex-1`}
        />
        <Button type="submit" kind={service.sign_in ? 'tinted' : 'filled'} disabled={!key.trim() || busy}>
          {busy ? 'Checking…' : 'Connect'}
        </Button>
      </form>
      <div className="flex items-center justify-between">
        <Button kind="plain" className="px-0" onClick={() => void llmSettingsService.openKeyPage(service.id)}>
          Get a key <ExternalLink className="w-3.5 h-3.5" aria-hidden />
        </Button>
        <span className="t-caption text-label-2">Stored in your system's secure keychain</span>
      </div>
      {message && <p className={`t-footnote ${message.error ? 'text-danger' : 'text-label-2'}`}>{message.text}</p>}
    </div>
  );
};

export const BrainSettings: React.FC = () => {
  const [settings, setSettings] = useState<LLMSettings | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [editingRole, setEditingRole] = useState<Role | null>(null);
  const [openService, setOpenService] = useState<string | null>(null);
  const [tests, setTests] = useState<Partial<Record<Role, string>>>({});

  const refresh = useCallback(async () => {
    try {
      setSettings(await llmSettingsService.get());
      setLoadError(null);
    } catch (err) {
      setLoadError(errorDetail(err, "HARIKA's engine isn't running, so model settings can't be shown."));
    }
  }, []);

  useEffect(() => {
    void refresh();
    // Sign-in finishes in the browser; the backend announces it here.
    const source = new EventSource(`${env.API_BASE_URL}/events`);
    source.addEventListener('llm_settings_changed', () => {
      setOpenService(null);
      void refresh();
    });
    return () => source.close();
  }, [refresh]);

  const runTest = async (role: Role) => {
    setTests((t) => ({ ...t, [role]: 'Testing…' }));
    try {
      const result = await llmSettingsService.test(role);
      const seconds = (result.latency_ms / 1000).toFixed(1);
      setTests((t) => ({ ...t, [role]: result.ok ? `Answered in ${seconds} s` : result.reply }));
    } catch (err) {
      setTests((t) => ({ ...t, [role]: errorDetail(err, 'The test request failed.') }));
    }
  };

  const disconnect = async (service: LLMService) => {
    setSettings(await llmSettingsService.disconnect(service.id));
    setOpenService(null);
  };

  if (loadError) return <p className="t-callout text-label-2">{loadError}</p>;
  if (!settings) return <p className="t-callout text-label-2">Loading…</p>;

  return (
    <div className="space-y-7">
      <GroupedSection
        title="Models HARIKA uses"
        footer="With a cloud model, what you ask is sent to that service. On-device models keep everything on this computer."
      >
        {(Object.keys(ROLE_COPY) as Role[]).map((role) => {
          const choice = settings.roles[role];
          return (
            <div key={role}>
              <Row
                title={ROLE_COPY[role].title}
                subtitle={
                  <>
                    <span className="block">{ROLE_COPY[role].hint}</span>
                    <span className="flex flex-wrap items-center gap-2 mt-1.5">
                      <span className="text-label truncate">{choice.model || 'No model chosen'}</span>
                      <PlaceBadge onDevice={choice.on_device} />
                      {tests[role] && <span>{tests[role]}</span>}
                    </span>
                  </>
                }
                accessory={
                  <span className="flex gap-1">
                    <Button kind="plain" onClick={() => void runTest(role)}>Test</Button>
                    <Button kind="tinted" onClick={() => setEditingRole(editingRole === role ? null : role)}>Change</Button>
                  </span>
                }
              />
              {editingRole === role && (
                <RoleEditor
                  role={role}
                  settings={settings}
                  onCancel={() => setEditingRole(null)}
                  onSaved={(next) => {
                    setSettings(next);
                    setEditingRole(null);
                    setTests((t) => ({ ...t, [role]: undefined }));
                  }}
                />
              )}
            </div>
          );
        })}
      </GroupedSection>

      <GroupedSection footer="If the chosen service is offline or busy, HARIKA quietly asks your other connected services, then the model on this computer.">
        <Row
          title="Use backups automatically"
          accessory={
            <Toggle
              label="Use backups automatically"
              checked={settings.use_backups}
              onChange={(on) => void llmSettingsService.setBackups(on).then(setSettings)}
            />
          }
        />
      </GroupedSection>

      <GroupedSection title="Services" footer="Connect a service to choose its models above. ChatGPT Plus and Claude Pro subscriptions can't be used by other apps, so cloud services need their own API key or sign-in.">
        {settings.services.map((service) => (
          <div key={service.id}>
            <Row
              title={service.name}
              subtitle={service.blurb}
              accessory={
                service.connected ? (
                  <span className="flex items-center gap-2">
                    <span className="flex items-center gap-1 t-footnote text-ok">
                      <Check className="w-4 h-4" aria-hidden /> {service.needs_key ? 'Connected' : 'Ready'}
                    </span>
                    {service.needs_key && (
                      <Button kind="plain" destructive onClick={() => void disconnect(service)}>Disconnect</Button>
                    )}
                  </span>
                ) : !service.needs_key ? (
                  <span className="t-footnote text-label-2" title="Start it on this computer, then reopen Settings.">
                    Not running
                  </span>
                ) : (
                  <Button kind="tinted" onClick={() => setOpenService(openService === service.id ? null : service.id)}>
                    {service.sign_in ? 'Sign in' : 'Connect'}
                  </Button>
                )
              }
            />
            {openService === service.id && !service.connected && (
              <ServiceConnect service={service} onDone={() => { setOpenService(null); void refresh(); }} />
            )}
          </div>
        ))}
      </GroupedSection>
    </div>
  );
};
