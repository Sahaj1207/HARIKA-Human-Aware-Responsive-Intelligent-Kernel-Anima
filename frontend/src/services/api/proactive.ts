import { apiClient } from './client';

export interface ProactiveSettings {
  meetings: boolean;
  meeting_minutes: number;
  birthdays: boolean;
  battery: boolean;
  battery_percent: number;
  /** No heads-ups (except low battery) between quiet_start and quiet_end. */
  quiet_hours: boolean;
  quiet_start: string;
  quiet_end: string;
  /** Habit suggestions at most this many times a day. */
  suggestions_per_day: number;
}

export const proactiveService = {
  async get(): Promise<ProactiveSettings> {
    return (await apiClient.get<ProactiveSettings>('/settings/proactive')).data;
  },
  async update(changes: Partial<ProactiveSettings>): Promise<ProactiveSettings> {
    return (await apiClient.put<ProactiveSettings>('/settings/proactive', changes)).data;
  },
};
