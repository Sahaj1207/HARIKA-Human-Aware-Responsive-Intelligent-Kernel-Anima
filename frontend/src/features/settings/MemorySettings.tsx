import React, { useEffect, useState } from 'react';
import { X } from 'lucide-react';
import { GroupedSection, Row, Toggle } from '@/components/apple/controls';
import { env } from '@/config/env';
import { memoryService, type MemoryItemApi, type MemoryOverview } from '@/services/api/memory';

const KIND: Record<string, string> = {
  user_profile: 'About you',
  preferences: 'Likes',
  goals: 'Plans',
  projects: 'Projects',
  relationships: 'People',
  skills: 'Skills',
  notes: 'Notes',
  tasks: 'Tasks',
};

const Wrap: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <span className="whitespace-normal">{children}</span>
);

const ForgetButton: React.FC<{ label: string; onClick: () => void }> = ({ label, onClick }) => (
  <button
    type="button"
    onClick={onClick}
    aria-label={label}
    title={label}
    className="w-6 h-6 shrink-0 grid place-items-center rounded-full text-label-3 hover:text-danger hover:bg-fill transition-colors"
  >
    <X className="w-3.5 h-3.5" />
  </button>
);

/** Settings > Memory: what HARIKA remembers, and the switches for it. */
export const MemorySettings: React.FC = () => {
  const [memory, setMemory] = useState<MemoryOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [showAllDays, setShowAllDays] = useState(false);

  useEffect(() => {
    const load = () =>
      memoryService
        .overview()
        .then(setMemory)
        .catch(() => setError("HARIKA's engine isn't running, so memories can't be shown."));
    void load();
    // Stays current while open: HARIKA may learn something from a chat in another window.
    const source = new EventSource(`${env.API_BASE_URL}/events`);
    source.addEventListener('memory', () => void load());
    return () => source.close();
  }, []);

  const run = async (change: () => Promise<MemoryOverview>) => {
    try {
      setMemory(await change());
      setError(null);
    } catch {
      setError("Couldn't make that change. Try again.");
    }
  };

  if (!memory) {
    return error ? (
      <GroupedSection>
        <Row title={error} />
      </GroupedSection>
    ) : null;
  }

  const { settings } = memory;
  const days = showAllDays ? memory.days : memory.days.slice(0, 5);
  const factRow = (fact: MemoryItemApi) => (
    <Row
      key={fact.id}
      title={<Wrap>{fact.content}</Wrap>}
      subtitle={KIND[fact.category] ?? 'Notes'}
      accessory={<ForgetButton label={`Forget “${fact.content}”`} onClick={() => void run(() => memoryService.forget(fact.id))} />}
    />
  );

  return (
    <div className="space-y-7">
      {error && (
        <GroupedSection>
          <Row title={error} />
        </GroupedSection>
      )}

      <GroupedSection
        footer={`Kept on this computer for ${memory.retention_days} days, so you can ask things like “what did we talk about yesterday?”. Each finished day is summarised once by your conversation model.`}
      >
        <Row
          title="Remember our conversations"
          subtitle={
            memory.journal_days
              ? `${memory.journal_days} day${memory.journal_days === 1 ? '' : 's'} remembered.`
              : 'Nothing remembered yet.'
          }
          accessory={
            <Toggle
              label="Remember our conversations"
              checked={settings.remember_conversations}
              onChange={(on) => void run(() => memoryService.update({ remember_conversations: on }))}
            />
          }
        />
        <Row
          title="Notice habits"
          subtitle="Mentions things you usually ask for at about this time. HARIKA never does them on its own."
          accessory={
            <Toggle
              label="Notice habits"
              checked={settings.notice_habits}
              onChange={(on) => void run(() => memoryService.update({ notice_habits: on }))}
            />
          }
        />
      </GroupedSection>

      <GroupedSection
        title="What HARIKA knows about you"
        footer={memory.facts.length ? 'HARIKA uses these in its replies. Remove anything that is wrong.' : undefined}
      >
        {memory.facts.length ? (
          memory.facts.map(factRow)
        ) : (
          <Row title="Nothing yet" subtitle="Tell HARIKA things like “remember that I love dosa”, or just talk. It learns from each day." />
        )}
      </GroupedSection>

      {memory.habits.length > 0 && (
        <GroupedSection title="Habits" footer="Remove a habit and HARIKA won't mention it again.">
          {memory.habits.map((habit) => (
            <Row
              key={habit.id}
              title={<Wrap>{habit.description}</Wrap>}
              accessory={
                <ForgetButton
                  label={`Not a habit: ${habit.description}`}
                  onClick={() => void run(() => memoryService.dismissHabit(habit.id))}
                />
              }
            />
          ))}
        </GroupedSection>
      )}

      {memory.days.length > 0 && (
        <GroupedSection title="Your days">
          {days.map((day) => (
            <Row
              key={day.id}
              title={day.title}
              subtitle={day.content}
              accessory={<ForgetButton label={`Forget ${day.title}`} onClick={() => void run(() => memoryService.forget(day.id))} />}
            />
          ))}
          {memory.days.length > 5 && !showAllDays && (
            <Row title={`Show all ${memory.days.length} days`} chevron onClick={() => setShowAllDays(true)} />
          )}
        </GroupedSection>
      )}

      <GroupedSection footer="Erases the conversation journal, day summaries, everything HARIKA learned about you and its habits. People, notes, routines and reminders are kept.">
        <Row
          title={confirming ? 'Click again to forget everything' : 'Forget everything'}
          destructive
          onClick={() => {
            if (!confirming) {
              setConfirming(true);
              return;
            }
            setConfirming(false);
            void run(memoryService.forgetEverything);
          }}
        />
      </GroupedSection>
    </div>
  );
};
