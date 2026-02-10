/** Application constants. */
import Constants from 'expo-constants';

const configApiUrl = Constants.expoConfig?.extra?.apiBaseUrl as string | null;

export const API_BASE_URL = configApiUrl
  ? `${configApiUrl}/api/v1`
  : __DEV__
    ? 'http://localhost:8000/api/v1'
    : 'https://eha-production-abc123.up.railway.app/api/v1';

export const STORAGE_KEYS = {
  ACCESS_TOKEN: 'eha_access_token',
  REFRESH_TOKEN: 'eha_refresh_token',
  USER: 'eha_user',
} as const;

export const DEFAULT_REMINDER_MINUTES = [60, 15] as const;

export const URGENCY_COLORS = {
  low: '#4CAF50',
  medium: '#FF9800',
  high: '#F44336',
} as const;

export const TONE_LABELS: Record<string, string> = {
  formal: 'Formal',
  friendly: 'Friendly',
  brief: 'Brief',
};
