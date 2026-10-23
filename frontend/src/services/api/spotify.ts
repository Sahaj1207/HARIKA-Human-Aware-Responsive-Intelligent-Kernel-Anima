import { apiClient } from './client';

export interface SpotifyStatus {
  /** A Client ID is set (the user's own, or one built into HARIKA). */
  configured: boolean;
  own_client: boolean;
  connected: boolean;
  /** The Spotify account's display name. */
  name: string;
  /** Spotify only lets apps control playback on Premium accounts. */
  premium: boolean;
  /** The exact address to register as the app's Redirect URI. */
  redirect_uri: string;
}

export const spotifyService = {
  async status(): Promise<SpotifyStatus> {
    return (await apiClient.get<{ spotify: SpotifyStatus }>('/accounts')).data.spotify;
  },
  async setClient(client_id: string): Promise<SpotifyStatus> {
    return (await apiClient.put<{ spotify: SpotifyStatus }>('/accounts/spotify/client', { client_id })).data.spotify;
  },
  /** Opens Spotify's sign-in page in the browser; the result arrives as an "accounts_changed" event. */
  async signIn(): Promise<void> {
    await apiClient.post('/accounts/spotify/sign-in');
  },
  async disconnect(): Promise<SpotifyStatus> {
    return (await apiClient.delete<{ spotify: SpotifyStatus }>('/accounts/spotify')).data.spotify;
  },
  async openSetupPage(): Promise<void> {
    await apiClient.post('/accounts/spotify/setup-page');
  },
};
