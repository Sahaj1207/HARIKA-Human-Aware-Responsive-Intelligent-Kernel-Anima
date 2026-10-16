import { apiClient } from './client';

export interface GoogleStatus {
  /** The user's own Google OAuth client has been added. */
  configured: boolean;
  connected: boolean;
  email: string;
  calendar: boolean;
  email_read: boolean;
  email_send: boolean;
}

export const accountsService = {
  async status(): Promise<GoogleStatus> {
    return (await apiClient.get<{ google: GoogleStatus }>('/accounts')).data.google;
  },
  async setGoogleClient(client_id: string, client_secret: string): Promise<GoogleStatus> {
    return (await apiClient.put<{ google: GoogleStatus }>('/accounts/google/client', { client_id, client_secret })).data.google;
  },
  /** Opens Google's sign-in page in the browser; the result arrives as an "accounts_changed" event. */
  async signInWithGoogle(): Promise<void> {
    await apiClient.post('/accounts/google/sign-in');
  },
  async disconnectGoogle(): Promise<GoogleStatus> {
    return (await apiClient.delete<{ google: GoogleStatus }>('/accounts/google')).data.google;
  },
};

/** Opens Google Cloud Console in the browser, for the one-time OAuth client setup. */
export async function openGoogleSetupPage(): Promise<void> {
  await apiClient.post('/accounts/google/setup-page');
}
