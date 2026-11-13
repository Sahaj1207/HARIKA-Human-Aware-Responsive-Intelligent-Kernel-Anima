import React, { useEffect, useState } from 'react';
import { Check, CircleAlert, CircleHelp, Hand, Minus } from 'lucide-react';
import { GroupedSection, Row, Segmented, Toggle } from '@/components/apple/controls';
import { activityService, type ActivityEntry, type ActivityOverview } from '@/services/api/activity';

const DAYS_SHOWN = 7;

/** The mark beside an entry: done, failed, waiting on the user, handed to them, or not done. */
const Mark: React.FC<{ entry: ActivityEntry }> = ({ entry }) => {
  const icon = 'w-4 h-4 shrink-0';
  if (entry.result === 'failed') return <CircleAlert className={icon} style={{ color: 'var(--red)' }} aria-label="Failed" />;
  if (entry.result === 'asked you') return <CircleHelp className={icon} style={{ color: 'var(--orange)' }} aria-label="Asked you" />;
  if (entry.result === 'handed to you') return <Hand className={icon} style={{ color: 'var(--blue)' }} aria-label="Handed to you" />;
  if (entry.result === 'not done') return <Minus className={`${icon} text-label-3`} aria-label="Not done" />;
  return <Check className={icon} style={{ color: 'var(--green)' }} aria-label="Done" />;
};

function dayLabel(iso: string): string {
  const day = new Date(iso);
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);
  if (day.toDateString() === today.toDateString()) return 'Today';
  if (day.toDateString() === yesterday.toDateString()) return 'Yesterday';
  return day.toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long' });
}

function clock(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
}

/** "Because you asked · you said yes · done", leaving out what goes without saying. */
function summary(entry: ActivityEntry): string {
  const parts = [entry.why === 'routine' ? 'A routine ran it' : entry.why === 'reminder' ? 'A reminder' : `Because ${entry.why}`];
  if (entry.approval !== 'not needed' && entry.approval !== entry.result) parts.push(entry.approval);
  parts.push(entry.result);
  return parts.join(' · ');
}

const EntryRow: React.FC<{ entry: ActivityEntry }> = ({ entry }) => {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="w-full flex items-center gap-3 px-4 py-2.5 text-left hover:bg-fill/60 transition-colors"
      >
        <Mark entry={entry} />
        <span className="flex-1 min-w-0 t-callout text-label truncate">{entry.what}</span>
        <span className="t-footnote text-label-2 shrink-0">{clock(entry.time)}</span>
      </button>
      {open && (
        <div className="px-11 pb-3 -mt-1 space-y-0.5">
          <p className="t-footnote text-label-2">{summary(entry)}</p>
          {entry.detail && <p className="t-footnote text-label-2">{entry.detail}</p>}
        </div>
      )}
    </div>
  );
};

/** Settings > Activity: what HARIKA did, why, whether it needed a yes, and how it went. */
export const ActivitySettings: React.FC = () => {
  const [overview, setOverview] = useState<ActivityOverview | null>(null);
  const [filter, setFilter] = useState<'all' | 'approval'>('all');
  const [confirmingClear, setConfirmingClear] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    const load = () =>
      activityService
        .get(DAYS_SHOWN, filter === 'approval')
        .then((next) => alive && (setOverview(next), setError(null)))
        .catch(() => alive && setError("HARIKA's engine isn't running, so her activity can't be shown."));
    void load();
    const timer = setInterval(load, 5000); // new entries appear while the page is open
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [filter]);

  const change = async (run: () => Promise<ActivityOverview>) => {
    try {
      await run();
      setOverview(await activityService.get(DAYS_SHOWN, filter === 'approval'));
    } catch {
      setError("Couldn't make that change. Try again.");
    }
  };

  if (!overview) {
    return error ? (
      <GroupedSection>
        <Row title={error} />
      </GroupedSection>
    ) : null;
  }

  const days: { label: string; entries: ActivityEntry[] }[] = [];
  for (const entry of overview.entries) {
    const label = dayLabel(entry.time);
    if (days[days.length - 1]?.label !== label) days.push({ label, entries: [] });
    days[days.length - 1].entries.push(entry);
  }

  return (
    <div className="space-y-7">
      <Segmented<'all' | 'approval'>
        label="Show"
        value={filter}
        onChange={setFilter}
        options={[
          { value: 'all', label: 'Everything' },
          { value: 'approval', label: 'Needed my yes' },
        ]}
      />

      {days.length === 0 ? (
        <GroupedSection>
          <Row
            title={filter === 'approval' ? 'Nothing needed your yes this week' : 'Nothing yet'}
            subtitle={overview.keep ? 'What HARIKA does for you will show up here.' : 'Activity history is off.'}
          />
        </GroupedSection>
      ) : (
        days.map((day) => (
          <GroupedSection key={day.label} title={day.label}>
            {day.entries.map((entry, index) => (
              <EntryRow key={`${entry.time}-${index}`} entry={entry} />
            ))}
          </GroupedSection>
        ))
      )}

      <GroupedSection
        footer={`Only what HARIKA did, never what you said. Kept on this computer for ${overview.keep_days} days.`}
      >
        <Row
          title="Keep an activity history"
          accessory={
            <Toggle
              label="Keep an activity history"
              checked={overview.keep}
              onChange={(keep) => void change(() => activityService.setKeeping(keep))}
            />
          }
        />
        <Row
          title={confirmingClear ? 'Tap again to clear' : 'Clear activity history'}
          destructive
          onClick={() => {
            if (!confirmingClear) {
              setConfirmingClear(true);
              return;
            }
            setConfirmingClear(false);
            void change(activityService.clear);
          }}
        />
      </GroupedSection>
      {error && <p className="t-footnote text-danger">{error}</p>}
    </div>
  );
};
