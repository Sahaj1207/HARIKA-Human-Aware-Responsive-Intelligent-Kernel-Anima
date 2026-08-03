export interface UserProfile {
  name: string;
}

const STORAGE_KEY = 'harika_user';

export const userStorage = {
  getProfile(): UserProfile | null {
    try {
      const data = localStorage.getItem(STORAGE_KEY);
      if (!data) return null;
      return JSON.parse(data) as UserProfile;
    } catch {
      return null;
    }
  },

  saveProfile(profile: UserProfile): void {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(profile));
    } catch (e) {
      console.error('Failed to save user profile to localStorage', e);
    }
  },

  clearProfile(): void {
    localStorage.removeItem(STORAGE_KEY);
  },
};
