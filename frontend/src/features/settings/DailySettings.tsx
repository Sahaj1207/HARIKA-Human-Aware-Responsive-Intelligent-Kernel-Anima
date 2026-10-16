import React, { useEffect, useState } from 'react';
import { GroupedSection, Row, Toggle } from '@/components/apple/controls';
import { dailyService, type DailySettings } from '@/services/api/daily';

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
