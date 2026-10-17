import React, { useEffect, useState } from 'react';
import { GroupedSection, Row, Toggle } from '@/components/apple/controls';
import { dailyService, type DailySettings } from '@/services/api/daily';
import { proactiveService, type ProactiveSettings } from '@/services/api/proactive';

/** Settings > General: where "the weather" means, and the morning briefing. */
export const DailySection: React.FC = () => {
  const [settings, setSettings] = useState<DailySettings | null>(null);
  const [home, setHome] = useState('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    dailyService
      .get()
      .then((loaded) => {
        setSettings(loaded);
        setHome(loaded.home);
      })
      .catch(() => setError("HARIKA's engine isn't running, so these settings can't be shown."));
  }, []);

  const save = async (changes: Partial<DailySettings>) => {
    try {
      setSettings(await dailyService.update(changes));
      setError(null);
    } catch {
      setError("Couldn't save that change. Try again.");
    }
  };

  if (!settings) {
    return error ? (
      <GroupedSection title="Your day">
        <Row title={error} />
      </GroupedSection>
    ) : null;
  }

  return (
    <GroupedSection
      title="Your day"
      footer={
        error ??
        'Ask "brief me" any time for the weather, today\'s reminders and the headlines. Leave the city empty to use your approximate location.'
      }
    >
      <Row
        title="Home city"
        accessory={
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void save({ home: home.trim() });
            }}
          >
            <input
              value={home}
              maxLength={80}
              placeholder="Automatic"
              onChange={(e) => setHome(e.target.value)}
              onBlur={() => home.trim() !== settings.home && void save({ home: home.trim() })}
              aria-label="Home city for weather"
              className="w-44 text-right bg-transparent t-callout text-label-2 outline-none focus:text-label placeholder:text-label-3"
            />
          </form>
        }
      />
      <Row
        title="Morning briefing"
        subtitle="Shown, and spoken if voice is on, once a day."
        accessory={
          <Toggle
            label="Morning briefing"
            checked={settings.briefing_enabled}
            onChange={(checked) => void save({ briefing_enabled: checked })}
          />
        }
      />
      {settings.briefing_enabled && (
        <Row
          title="Time"
          accessory={
            <input
              type="time"
              value={settings.briefing_time}
              onChange={(e) => e.target.value && void save({ briefing_time: e.target.value })}
              aria-label="Briefing time"
              className="bg-transparent t-callout text-label-2 outline-none focus:text-label"
            />
          }
        />
      )}
    </GroupedSection>
  );
};

/** Settings > General: what HARIKA may tell you about on its own. */
export const HeadsUpSection: React.FC = () => {
  const [settings, setSettings] = useState<ProactiveSettings | null>(null);

  useEffect(() => {
    proactiveService.get().then(setSettings).catch(() => setSettings(null));
  }, []);

  if (!settings) return null;
  const save = async (changes: Partial<ProactiveSettings>) => setSettings(await proactiveService.update(changes));

  return (
    <GroupedSection
      title="Heads-up"
      footer="HARIKA tells you about these on its own: in this window, as a notification, and out loud if you use “Hey HARIKA”."
    >
      <Row
        title="Upcoming meetings"
        subtitle="From your Google Calendar (Settings > Accounts)."
        accessory={
          <div className="flex items-center gap-3">
            {settings.meetings && (
              <select
                value={settings.meeting_minutes}
                onChange={(e) => void save({ meeting_minutes: Number(e.target.value) })}
                aria-label="Minutes before a meeting"
                className="bg-transparent t-callout text-label-2 outline-none"
              >
                {[5, 10, 15, 30].map((m) => (
                  <option key={m} value={m}>
                    {m} min before
                  </option>
                ))}
              </select>
            )}
            <Toggle label="Upcoming meetings" checked={settings.meetings} onChange={(on) => void save({ meetings: on })} />
          </div>
        }
      />
      <Row
        title="Birthdays"
        subtitle="People you've told HARIKA about, on the morning of their birthday."
        accessory={<Toggle label="Birthdays" checked={settings.birthdays} onChange={(on) => void save({ birthdays: on })} />}
      />
      <Row
        title="Low battery"
        subtitle={`When the battery drops to ${settings.battery_percent}% and isn't charging.`}
        accessory={<Toggle label="Low battery" checked={settings.battery} onChange={(on) => void save({ battery: on })} />}
      />
    </GroupedSection>
  );
};
