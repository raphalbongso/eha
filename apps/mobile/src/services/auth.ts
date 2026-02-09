/** Google OAuth PKCE flow for mobile. */

import * as WebBrowser from 'expo-web-browser';

import type { TokenResponse, User } from '../types';
import api from './api';
import { saveTokens, saveUser, clearAll } from './storage';

WebBrowser.maybeCompleteAuthSession();

interface AuthStartResponse {
  auth_url: string;
  state: string;
}

export async function startGoogleAuth(): Promise<TokenResponse> {
  // Step 1: Get auth URL from backend
  const { data } = await api.post<AuthStartResponse>('/auth/google/start');

  // Step 2: Open browser for Google consent
  const result = await WebBrowser.openAuthSessionAsync(
    data.auth_url,
    'eha://auth/callback',
  );

  if (result.type !== 'success' || !result.url) {
    throw new Error('Authentication cancelled or failed');
  }

  // Step 3: Extract code from callback URL
  const url = new URL(result.url);
  const code = url.searchParams.get('code');
  const state = url.searchParams.get('state');

  if (!code || !state) {
    throw new Error('Missing code or state in callback');
  }

  // Step 4: Exchange code for tokens via backend
  // Note: code_verifier should be passed from the start response in production.
  // In the PKCE flow, the backend generates and stores the code_verifier,
  // but the mobile app needs to pass it back. For the MVP, the backend
  // handles this via the state parameter mapping.
  const { data: tokens } = await api.post<TokenResponse>(
    '/auth/google/callback',
    {
      code,
      state,
      code_verifier: state, // Backend maps state to code_verifier
    },
  );

  // Step 5: Store tokens
  await saveTokens(tokens.access_token, tokens.refresh_token);

  return tokens;
}

export async function fetchCurrentUser(): Promise<User> {
  const { data } = await api.get<User>('/auth/me');
  await saveUser(data);
  return data;
}

export async function logout(): Promise<void> {
  await clearAll();
}

export async function refreshAccessToken(
  refreshToken: string,
): Promise<TokenResponse> {
  const { data } = await api.post<TokenResponse>('/auth/refresh', {
    refresh_token: refreshToken,
  });
  await saveTokens(data.access_token, data.refresh_token);
  return data;
}
