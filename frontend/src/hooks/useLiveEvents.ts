import { useEffect } from 'react';
import { env } from '@/config/env';
import { useHARIKAStore } from '@/store/useHARIKAStore';
import { notificationService } from '@/core/crystal/notifications/notificationService';

interface StepEvent {
  index: number;
  total: number;
  status: 'started' | 'completed' | 'failed' | 'skipped';
  label: string;
}

interface ReminderEvent {
  id: string;
  text: string;
}

/**
 * Subscribes to the backend's live event stream (/events):
 * step progress while HARIKA acts, reminders when they fall due, and the morning briefing.
 * EventSource reconnects on its own if the backend restarts.
 * Only one window should announce reminders, so other windows pass false.
 */
export function useLiveEvents({ announceReminders = true }: { announceReminders?: boolean } = {}): void {
  useEffect(() => {
    const source = new EventSource(`${env.API_BASE_URL}/events`);
    const { setActivity, addMessage } = useHARIKAStore.getState();
    let clearTimer: ReturnType<typeof setTimeout> | undefined;

    source.addEventListener('step', (raw) => {
      const step: StepEvent = JSON.parse((raw as MessageEvent).data);
      clearTimeout(clearTimer);
      const prefix = step.total > 1 ? `Step ${step.index}/${step.total}: ` : '';
      // Plain conversation is already shown as "Thinking…"; only real actions get a label.
      if (step.label === 'thinking' && step.total === 1) return;
      const label = step.label.charAt(0).toUpperCase() + step.label.slice(1);
      if (step.status === 'started') {
        setActivity(`${prefix}${label}…`);
      } else if (step.index === step.total || step.status !== 'completed') {
        // Leave the last outcome visible briefly, then clear.
        setActivity(step.status === 'completed' ? null : `${prefix}${label} (${step.status})`);
        clearTimer = setTimeout(() => setActivity(null), 3000);
      }
    });

    // Conversations started with "Hey HARIKA" join the main window's history.
    source.addEventListener('voice', (raw) => {
      if (!announceReminders) return;
      const event = JSON.parse((raw as MessageEvent).data);
      if (event.stage === 'answered' && event.text) {
        addMessage({ role: 'user', content: event.text, metadata: { provider: 'voice' } });
        if (event.reply) addMessage({ role: 'assistant', content: event.reply, metadata: { provider: 'voice' } });
      }
    });

    // Progress of a multi-step task ("Searching: laptops under 60k").
    source.addEventListener('activity', (raw) => {
      const { text, stoppable } = JSON.parse((raw as MessageEvent).data) as { text: string; stoppable?: boolean };
      clearTimeout(clearTimer);
      setActivity(text ? `${text}…` : null);
      useHARIKAStore.getState().setTaskRunning(Boolean(text && stoppable));
    });

    // Heads-ups HARIKA gives on its own (meetings, birthdays, battery).
    source.addEventListener('heads_up', (raw) => {
      if (!announceReminders) return;
      const { text } = JSON.parse((raw as MessageEvent).data) as { text: string };
      notificationService.show('info', 'Heads up', text, 10000);
      addMessage({ role: 'assistant', content: text, metadata: { provider: 'heads-up' } });
    });

    // A routine that ran on its schedule ("every weekday at 9").
    source.addEventListener('routine', (raw) => {
      if (!announceReminders) return;
      const { name, text } = JSON.parse((raw as MessageEvent).data) as { name: string; text: string };
      notificationService.show('info', `Ran “${name}”`, text, 8000);
      const content = text ? `Ran “${name}”.\n\n${text}` : `Ran “${name}”.`;
      addMessage({ role: 'assistant', content, metadata: { provider: 'routines' } });
    });

    // The morning briefing (Settings > General > Your day).
    source.addEventListener('briefing', (raw) => {
      if (!announceReminders) return;
      const { text } = JSON.parse((raw as MessageEvent).data) as { text: string };
      notificationService.show('info', 'Your day', text.split('\n\n')[0], 8000);
      addMessage({ role: 'assistant', content: text, metadata: { provider: 'briefing' } });
    });

    source.addEventListener('reminder', (raw) => {
      if (!announceReminders) return;
      const reminder: ReminderEvent = JSON.parse((raw as MessageEvent).data);
      notificationService.show('info', 'Reminder', reminder.text, 0);
      addMessage({ role: 'assistant', content: reminder.text, metadata: { provider: 'reminders' } });
    });

    return () => {
      clearTimeout(clearTimer);
      source.close();
    };
  }, [announceReminders]);
}
