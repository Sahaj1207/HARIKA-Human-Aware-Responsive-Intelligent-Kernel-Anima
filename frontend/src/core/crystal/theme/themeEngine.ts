import { DesignTokens } from '../tokens/designTokens';

export type ThemeMode = 'dark' | 'light' | 'system';

export interface ThemeConfig {
  mode: ThemeMode;
  highContrast: boolean;
  reducedMotion: boolean;
  fontSizeMultiplier: number;
}

const STORAGE_KEY = 'harika_crystal_theme_config';

const defaultThemeConfig: ThemeConfig = {
  mode: 'system',
  highContrast: false,
  reducedMotion: false,
  fontSizeMultiplier: 1.0,
};

export class ThemeEngine {
  private config: ThemeConfig;

  constructor() {
    this.config = this.loadConfig();
    this.applyTheme(this.config.mode);
    // "Automatic" follows the OS appearance live, like an Apple device at sunset.
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
      if (this.config.mode === 'system') this.applyTheme('system');
    });
  }

  public getConfig(): ThemeConfig {
    return { ...this.config };
  }

  public setMode(mode: ThemeMode): ThemeConfig {
    this.config.mode = mode;
    this.saveConfig();
    this.applyTheme(mode);
    return this.getConfig();
  }

  public setHighContrast(enabled: boolean): ThemeConfig {
    this.config.highContrast = enabled;
    this.saveConfig();
    document.documentElement.classList.toggle('high-contrast', enabled);
    return this.getConfig();
  }

  public setReducedMotion(enabled: boolean): ThemeConfig {
    this.config.reducedMotion = enabled;
    this.saveConfig();
    document.documentElement.classList.toggle('reduced-motion', enabled);
    return this.getConfig();
  }

  public exportSettings(): string {
    return JSON.stringify(this.config, null, 2);
  }

  public importSettings(jsonString: string): ThemeConfig {
    try {
      const parsed = JSON.parse(jsonString);
      if (parsed && typeof parsed === 'object') {
        this.config = { ...defaultThemeConfig, ...parsed };
        this.saveConfig();
        this.applyTheme(this.config.mode);
      }
    } catch {
      // Invalid JSON
    }
    return this.getConfig();
  }

  public resetSettings(): ThemeConfig {
    this.config = { ...defaultThemeConfig };
    this.saveConfig();
    this.applyTheme(this.config.mode);
    return this.getConfig();
  }

  private loadConfig(): ThemeConfig {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) return { ...defaultThemeConfig, ...JSON.parse(stored) };
    } catch {
      // Fallback
    }
    return { ...defaultThemeConfig };
  }

  private saveConfig(): void {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(this.config));
    } catch {
      // Ignore write errors
    }
  }

  private applyTheme(mode: ThemeMode): void {
    const isDark =
      mode === 'dark' ||
      (mode === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);

    document.documentElement.classList.toggle('dark', isDark);
    document.documentElement.classList.toggle('light', !isDark);

    // Inject DesignTokens CSS Custom Properties
    const root = document.documentElement;
    root.style.setProperty('--crystal-primary', DesignTokens.colors.primary);
    root.style.setProperty('--crystal-accent', DesignTokens.colors.accent);
    root.style.setProperty('--crystal-glow', DesignTokens.shadows.glow);
  }
}

export const themeEngine = new ThemeEngine();
