import axios from 'axios';
import { env } from '@/config/env';

export const apiClient = axios.create({
  baseURL: env.API_BASE_URL,
  timeout: 60000, // 60 seconds timeout to accommodate local LLM model inference
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use(
  (config) => {
    const fullUrl = `${config.baseURL?.replace(/\/$/, '')}/${config.url?.replace(/^\//, '')}`;
    // Never echo credentials into the console.
    const data = config.data && typeof config.data === 'object' && 'api_key' in config.data
      ? { ...config.data, api_key: '[redacted]' }
      : config.data;
    console.log(`[HARIKA API Request] Sending ${config.method?.toUpperCase()} to ${fullUrl}`, data);
    return config;
  },
  (error) => {
    console.error('[HARIKA API Request Error]', error);
    return Promise.reject(error);
  }
);

apiClient.interceptors.response.use(
  (response) => {
    const fullUrl = `${response.config.baseURL?.replace(/\/$/, '')}/${response.config.url?.replace(/^\//, '')}`;
    console.log(`[HARIKA API Response] ${response.status} from ${fullUrl}`, response.data);
    return response;
  },
  (error) => {
    const fullUrl = error.config
      ? `${error.config.baseURL?.replace(/\/$/, '')}/${error.config.url?.replace(/^\//, '')}`
      : 'API Endpoint';
    console.error(`[HARIKA API Error] Call to ${fullUrl} failed:`, error.message, error?.response?.data || '');
    return Promise.reject(error);
  }
);
