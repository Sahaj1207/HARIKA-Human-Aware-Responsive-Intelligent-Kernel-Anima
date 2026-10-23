import React, { useEffect, useState } from 'react';
import { AtSign, Hand, Mic, Settings as Gear, Sparkles, SquareTerminal, X } from 'lucide-react';
import { GroupedSection, IconTile, Row, Segmented } from '@/components/apple/controls';
import { HarikaOrb } from '@/components/apple/HarikaOrb';
import { BrainSettings } from './BrainSettings';
import { VoiceSettings } from './VoiceSettings';
import { AccountsSettings } from './AccountsSettings';
import { DailySection, HeadsUpSection, ScreenLookSection } from './DailySettings';
import { UpdatesSection } from './UpdatesSection';
import { themeEngine, ThemeMode } from '@/core/crystal/theme/themeEngine';
import { userStorage } from '@/features/onboarding/storage';
import { useHARIKAStore } from '@/store/useHARIKAStore';

type PageId = 'general' | 'brain' | 'voice' | 'accounts' | 'privacy' | 'developer';

const PAGES: { id: PageId; label: string; color: string; icon: React.ReactNode }[] = [
  { id: 'general', label: 'General', color: 'var(--gray)', icon: <Gear className="w-4 h-4" strokeWidth={2.25} /> },
  { id: 'brain', label: 'Brain', color: 'var(--purple)', icon: <Sparkles className="w-4 h-4" strokeWidth={2.25} /> },
  { id: 'voice', label: 'Voice', color: 'var(--pink)', icon: <Mic className="w-4 h-4" strokeWidth={2.25} /> },
  { id: 'accounts', label: 'Accounts', color: 'var(--orange)', icon: <AtSign className="w-4 h-4" strokeWidth={2.25} /> },
  { id: 'privacy', label: 'Privacy', color: 'var(--blue)', icon: <Hand className="w-4 h-4" strokeWidth={2.25} /> },
  { id: 'developer', label: 'Developer', color: 'var(--indigo)', icon: <SquareTerminal className="w-4 h-4" strokeWidth={2.25} /> },
];

const isMac = typeof navigator !== 'undefined' && /Mac/i.test(navigator.platform);
const SHORTCUT = isMac ? '⌃ ⇧ Space' : 'Ctrl + Shift + Space';

const GeneralPage: React.FC = () => {
  const [name, setName] = useState(userStorage.getProfile()?.name ?? '');
  const [mode, setMode] = useState<ThemeMode>(themeEngine.getConfig().mode);
  const [saved, setSaved] = useState(false);

  const saveName = () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    userStorage.saveProfile({ name: trimmed });
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  };

  return (
    <div className="space-y-7">
      <GroupedSection title="You">
        <Row
          title="Name"
          accessory={
            <form
              className="flex items-center gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                saveName();
              }}
            >
              <input
                value={name}
                maxLength={30}
                onChange={(e) => setName(e.target.value)}
                onBlur={saveName}
                aria-label="Your name"
                className="w-44 text-right bg-transparent t-callout text-label-2 outline-none focus:text-label"
              />
              {saved && <span className="t-footnote text-ok">Saved</span>}
            </form>
          }
        />
      </GroupedSection>

      <DailySection />

      <HeadsUpSection />

      <GroupedSection title="Appearance" footer="Automatic follows your computer's light and dark mode.">
        <Row
          title="Appearance"
          accessory={
            <Segmented<ThemeMode>
              label="Appearance"
              value={mode}
              onChange={(next) => setMode(themeEngine.setMode(next).mode)}
              options={[
                { value: 'system', label: 'Automatic' },
                { value: 'light', label: 'Light' },
                { value: 'dark', label: 'Dark' },
              ]}
            />
          }
        />
      </GroupedSection>

      <GroupedSection footer="Walks through connecting a brain, your city, the briefing, Google and the voice again.">
        <Row title="Run setup again" chevron onClick={() => window.dispatchEvent(new CustomEvent('harika:run-setup'))} />
      </GroupedSection>

      <UpdatesSection />

      <GroupedSection title="Desktop" footer="Start at login is in the HARIKA menu in your system tray.">
        <Row title="Ask HARIKA from anywhere" value={SHORTCUT} />
      </GroupedSection>
    </div>
  );
};

const PrivacyPage: React.FC = () => {
  const clearMessages = useHARIKAStore((s) => s.clearMessages);
  const [confirming, setConfirming] = useState(false);
  const [cleared, setCleared] = useState(false);
  return (
    <div className="space-y-7">
      <GroupedSection title="Where your information lives">
        <Row title="Conversations, memories and reminders" subtitle="Stored on this computer." />
        <Row title="API keys" subtitle={isMac ? 'Kept in your Keychain.' : 'Kept in Windows Credential Manager.'} />
        <Row title="Cloud models" subtitle="Only see the messages HARIKA sends them, and only when you choose one in Brain." />
        <Row
          title="Reading your screen"
          subtitle="Only when you ask, like &ldquo;continue this chat&rdquo;. The visible text goes to your conversation model, and nothing is sent in a chat until you say yes."
        />
      </GroupedSection>
      <ScreenLookSection />
      <GroupedSection footer="Removes the messages shown in this window. HARIKA's memories are kept.">
        <Row
          title={cleared ? 'Conversation cleared' : confirming ? 'Tap again to clear' : 'Clear conversation'}
          destructive={!cleared}
          onClick={() => {
            if (cleared) return;
            if (!confirming) {
              setConfirming(true);
              return;
            }
            clearMessages();
            setCleared(true);
          }}
        />
      </GroupedSection>
    </div>
  );
};

const DeveloperPage: React.FC<{ onOpenTelemetry: () => void }> = ({ onOpenTelemetry }) => (
  <div className="space-y-7">
    <GroupedSection footer="Live memory, tools, routing and agent internals, for debugging.">
      <Row title="Open system panel" chevron onClick={onOpenTelemetry} />
    </GroupedSection>
    <div className="flex flex-col items-center gap-3 pt-6 text-center">
      <HarikaOrb size={56} />
      <p className="t-headline">HARIKA</p>
      <p className="t-footnote text-label-2">Version 0.1.0</p>
    </div>
  </div>
);

export const SettingsWindow: React.FC<{ isOpen: boolean; onClose: () => void; initialPage?: PageId }> = ({
  isOpen,
  onClose,
  initialPage = 'general',
}) => {
  const [page, setPage] = useState<PageId>(initialPage);
  const toggleQuickPanel = useHARIKAStore((s) => s.toggleQuickPanel);

  // Reset to the first page only when the window opens, not on every re-render.
  useEffect(() => {
    if (isOpen) setPage(initialPage);
  }, [isOpen, initialPage]);

  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isOpen, onClose]);

  if (!isOpen) return null;
  const current = PAGES.find((p) => p.id === page)!;

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/25 dark:bg-black/50 p-4" onMouseDown={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Settings"
        onMouseDown={(e) => e.stopPropagation()}
        className="bubble-enter w-full max-w-[860px] h-[min(600px,90vh)] flex rounded-[18px] overflow-hidden bg-grouped dark:bg-surface shadow-[0_30px_90px_rgba(0,0,0,0.35),0_0_0_0.5px_var(--separator)]"
      >
        <nav className="w-56 shrink-0 glass !shadow-none !border-0 border-r border-separator p-3 pt-4 flex flex-col gap-0.5" aria-label="Settings sections">
          <button
            type="button"
            onClick={onClose}
            aria-label="Close settings"
            className="self-start mb-3 ml-1 w-3.5 h-3.5 rounded-full bg-[#FF5F57] grid place-items-center group"
          >
            <X className="w-2.5 h-2.5 opacity-0 group-hover:opacity-70 text-black" />
          </button>
          {PAGES.map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => setPage(p.id)}
              aria-current={page === p.id ? 'page' : undefined}
              className={`flex items-center gap-2.5 px-2 py-1.5 rounded-lg t-callout text-left transition-colors ${
                page === p.id ? 'bg-accent text-white' : 'text-label hover:bg-fill'
              }`}
            >
              <IconTile color={p.color}>{p.icon}</IconTile>
              {p.label}
            </button>
          ))}
        </nav>
        <section className="flex-1 overflow-y-auto px-8 py-6">
          <h2 className="t-title2 mb-6">{current.label}</h2>
          {page === 'general' && <GeneralPage />}
          {page === 'brain' && <BrainSettings />}
          {page === 'voice' && <VoiceSettings />}
          {page === 'accounts' && <AccountsSettings />}
          {page === 'privacy' && <PrivacyPage />}
          {page === 'developer' && (
            <DeveloperPage
              onOpenTelemetry={() => {
                onClose();
                toggleQuickPanel();
              }}
            />
          )}
        </section>
      </div>
    </div>
  );
};

export type { PageId as SettingsPageId };
