import { apiClient } from './client';

/** HARIKA's browser extension, for website tasks in your own Chrome or Edge. */
export interface ExtensionStatus {
  connected: boolean;
  browser: string;
  /** Pasted into the extension once, so only it can connect. */
  code: string;
  folder?: string;
}

export const browserService = {
  async status(): Promise<ExtensionStatus> {
    return (await apiClient.get<ExtensionStatus>('/browser/extension')).data;
  },
  async newCode(): Promise<ExtensionStatus> {
    return (await apiClient.post<ExtensionStatus>('/browser/extension/new-code')).data;
  },
  async openFolder(): Promise<ExtensionStatus> {
    return (await apiClient.post<ExtensionStatus>('/browser/extension/open-folder')).data;
  },
};
