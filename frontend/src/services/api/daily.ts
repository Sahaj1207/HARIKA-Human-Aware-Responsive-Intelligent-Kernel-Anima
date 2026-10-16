import { apiClient } from './client';

export interface DailySettings {
  /** City for weather; empty means the computer's approximate location. */
  home: string;
  briefing_enabled: boolean;
  /** 24-hour "HH:MM". */
  briefing_time: string;
}

export const dailyService = {
  async get(): Promise<DailySettings> {
    return (await apiClient.get<DailySettings>('/settings/daily')).data;
  },
  async update(changes: Partial<DailySettings>): Promise<DailySettings> {
    return (await apiClient.put<DailySettings>('/settings/daily', changes)).data;
  },
};
