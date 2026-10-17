import { apiClient } from './client';

export interface PrivacySettings {
  /** Capture the app you were using when you ask about it. */
  screen_images: boolean;
  /** Connected services that can look at images (empty: words on screen only). */
  vision_services: string[];
}

export const privacyService = {
  async get(): Promise<PrivacySettings> {
    return (await apiClient.get<PrivacySettings>('/settings/privacy')).data;
  },
  async update(changes: Partial<PrivacySettings>): Promise<PrivacySettings> {
    return (await apiClient.put<PrivacySettings>('/settings/privacy', changes)).data;
  },
};
