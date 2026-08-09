export const DesignTokens = {
  colors: {
    primary: '#0284c7',
    primaryGlow: 'rgba(2, 132, 199, 0.4)',
    accent: '#38bdf8',
    cyan: '#06b6d4',
    emerald: '#10b981',
    amber: '#f59e0b',
    rose: '#f43f5e',
    slate900: '#0f172a',
    slate800: '#1e293b',
    slate700: '#334155',
    slate400: '#94a3b8',
    slate200: '#e2e8f0',
    white: '#ffffff',
  },
  spacing: {
    xs: '4px',
    sm: '8px',
    md: '16px',
    lg: '24px',
    xl: '32px',
    xxl: '48px',
  },
  radius: {
    sm: '6px',
    md: '12px',
    lg: '16px',
    xl: '24px',
    full: '9999px',
  },
  blur: {
    sm: '4px',
    md: '12px',
    lg: '24px',
    xl: '40px',
  },
  shadows: {
    sm: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
    md: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
    lg: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
    xl: '0 20px 25px -5px rgba(0, 0, 0, 0.2), 0 10px 10px -5px rgba(0, 0, 0, 0.1)',
    glow: '0 0 25px rgba(56, 189, 248, 0.35)',
  },
  durations: {
    fast: '150ms',
    normal: '300ms',
    slow: '500ms',
    pulse: '2000ms',
  },
  opacity: {
    subtle: 0.1,
    medium: 0.25,
    strong: 0.6,
    solid: 1.0,
  },
} as const;

export type DesignTokensType = typeof DesignTokens;
