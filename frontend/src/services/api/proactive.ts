import { apiClient } from './client';

export interface ProactiveSettings {
  meetings: boolean;
  meeting_minutes: number;
  birthdays: boolean;
  battery: boolean;
  battery_percent: number;
}

export const proactiveService = {
  async get(): Promise<ProactiveSettings> {
    return (await apiClient.get<ProactiveSettings>('/settings/proactive')).data;
  },
  async update(changes: Partial<ProactiveSettings>): Promise<ProactiveSettings> {
    return (await apiClient.put<ProactiveSettings>('/settings/proactive', changes)).data;
  },
};
