import { apiClient } from './client';

export type SpeakReplies = 'voice' | 'always' | 'never';

export interface SpeechSettings {
  wake_word: boolean;
  /** After answering, keep listening a few seconds for a follow-up without "Hey HARIKA". */
  follow_up: boolean;
  /** Talking while HARIKA speaks stops her and becomes the next request. */
  barge_in: boolean;
  speak_replies: SpeakReplies;
  voice: string;
  speed: number;
  user_name: string;
  /** "piper" (offline) or "azure" (expressive). */
  engine: 'piper' | 'azure';
  azure_region: string;
  azure_voice: string;
}

export interface AzureVoice {
  id: string;
  name: string;
  accent: string;
}

export interface VoiceOption {
  id: string;
  name: string;
  accent: string;
  size_mb: number;
  downloaded: boolean;
}

export interface SpeechStatus {
  state: 'off' | 'idle' | 'listening' | 'thinking' | 'speaking';
  ready: boolean;
  missing_mb: number;
  downloading: boolean;
  settings: SpeechSettings;
  voices: VoiceOption[];
  /** A voice is available to speak with (offline or Azure). */
  can_speak: boolean;
  azure: { connected: boolean; region: string; voices: AzureVoice[] };
}

export const speechService = {
  async status(): Promise<SpeechStatus> {
    return (await apiClient.get<SpeechStatus>('/speech')).data;
  },
  async downloadModels(): Promise<SpeechStatus> {
    return (await apiClient.post<SpeechStatus>('/speech/models/download')).data;
  },
  async update(changes: Partial<SpeechSettings>): Promise<SpeechStatus> {
    return (await apiClient.put<SpeechStatus>('/speech/settings', changes)).data;
  },
  /** Records one spoken request (stops after a pause) and returns the words. */
  async listen(): Promise<string> {
    return (await apiClient.post<{ text: string }>('/speech/listen', undefined, { timeout: 40000 })).data.text;
  },
  /** followUpFor: the window of a push-to-talk conversation ("main", "orb"); HARIKA then listens for a follow-up. */
  async speak(text: string, tone?: string, followUpFor?: string): Promise<void> {
    await apiClient.post('/speech/speak', { text, tone, follow_up_for: followUpFor });
  },
  async connectAzure(key: string, region: string): Promise<SpeechStatus> {
    return (await apiClient.put<SpeechStatus>('/speech/azure', { key, region })).data;
  },
  async disconnectAzure(): Promise<SpeechStatus> {
    return (await apiClient.delete<SpeechStatus>('/speech/azure')).data;
  },
  async preview(voice: string): Promise<void> {
    await apiClient.post('/speech/preview', { voice });
  },
  async stop(): Promise<void> {
    await apiClient.post('/speech/stop');
  },
};

/** Speak a reply if the user's "Speak replies" setting calls for it. */
export async function speakReplyIfWanted(
  text: string,
  cameFromVoice: boolean,
  tone?: string,
  conversation?: string
): Promise<void> {
  try {
    const { settings, can_speak } = await speechService.status();
    if (!can_speak || settings.speak_replies === 'never') return;
    if (settings.speak_replies === 'voice' && !cameFromVoice) return;
    // A spoken request continues as a conversation: after the reply HARIKA listens for a follow-up.
    await speechService.speak(text, tone, cameFromVoice ? conversation : undefined);
  } catch {
    // Voice is optional; a failure here never affects the conversation.
  }
}
