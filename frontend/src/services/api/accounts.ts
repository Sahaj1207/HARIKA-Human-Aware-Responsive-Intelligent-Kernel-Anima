import { apiClient } from './client';

export interface GoogleStatus {
  /** A Google OAuth client is available (built into HARIKA, or the user's own). */
  configured: boolean;
  /** The user added their own client (Advanced). */
  own_client: boolean;
  /** This copy of HARIKA ships with a client, so people only need to sign in. */
  built_in_client: boolean;
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
  /** Stop using your own client and go back to HARIKA's built-in one. */
  async useBuiltInGoogleClient(): Promise<GoogleStatus> {
    return (await apiClient.delete<{ google: GoogleStatus }>('/accounts/google/client')).data.google;
  },
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
