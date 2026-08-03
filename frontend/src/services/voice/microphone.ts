export const microphoneService = {
  isSupported(): boolean {
    return (
      typeof window !== 'undefined' &&
      'navigator' in window &&
      'mediaDevices' in navigator &&
      typeof navigator.mediaDevices.getUserMedia === 'function'
    );
  },

  async checkPermissionState(): Promise<'granted' | 'denied' | 'prompt'> {
    if (typeof window === 'undefined' || !('navigator' in window) || !('permissions' in navigator)) {
      return 'prompt';
    }
    try {
      const status = await navigator.permissions.query({ name: 'microphone' as PermissionName });
      return status.state;
    } catch {
      return 'prompt';
    }
  },

  async requestPermission(): Promise<boolean> {
    if (!this.isSupported()) return false;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      // Clean up track references
      stream.getTracks().forEach((track) => track.stop());
      return true;
    } catch {
      return false;
    }
  },
};
