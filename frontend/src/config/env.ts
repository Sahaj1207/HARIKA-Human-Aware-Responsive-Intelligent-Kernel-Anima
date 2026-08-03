export const env = {
  APP_TITLE: import.meta.env.VITE_APP_TITLE || 'HARIKA AI OS',
  API_BASE_URL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1',
  ENABLE_MOCK: import.meta.env.VITE_ENABLE_MOCK === 'true',
} as const;
