import { apiClient } from './client';

/** One thing HARIKA did (or proposed), as Settings > Activity shows it. */
export interface ActivityEntry {
  time: string;
  /** In plain words: "Open calculator", "Click “Place your order”". */
  what: string;
  /** "you asked", "you said yes", "routine", "reminder". */
  why: string;
  /** "not needed", "you said yes", "you said no", "the question expired", "waiting for your yes", "handed to you". */
  approval: string;
  /** "done", "done, but I couldn't confirm it", "failed", "not done", "asked you", "handed to you". */
  result: string;
  detail: string;
}

export interface ActivityOverview {
  keep: boolean;
  keep_days: number;
  entries: ActivityEntry[];
}

export const activityService = {
  async get(days = 7, neededApproval = false): Promise<ActivityOverview> {
    return (await apiClient.get<ActivityOverview>('/activity', { params: { days, needed_approval: neededApproval } })).data;
  },
  async setKeeping(keep: boolean): Promise<ActivityOverview> {
    return (await apiClient.put<ActivityOverview>('/activity/settings', { keep })).data;
  },
  async clear(): Promise<ActivityOverview> {
    return (await apiClient.post<ActivityOverview>('/activity/clear')).data;
  },
};
