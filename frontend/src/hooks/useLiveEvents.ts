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
 * step progress while HARIKA acts, and reminders when they fall due.
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
      if (step.status === 'started') {
        setActivity(`${prefix}${step.label}…`);
      } else if (step.index === step.total || step.status !== 'completed') {
        // Leave the last outcome visible briefly, then clear.
        setActivity(step.status === 'completed' ? null : `${prefix}${step.label} (${step.status})`);
        clearTimer = setTimeout(() => setActivity(null), 3000);
      }
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
