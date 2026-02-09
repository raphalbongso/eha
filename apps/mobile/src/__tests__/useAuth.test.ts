/**
 * Tests for useAuth hook.
 */

import { renderHook, act, waitFor } from '@testing-library/react-native';

// Mock dependencies before importing hook
jest.mock('../services/storage', () => ({
  getAccessToken: jest.fn(),
  getUser: jest.fn(),
  clearAll: jest.fn(),
  saveUser: jest.fn(),
}));

jest.mock('../services/auth', () => ({
  startGoogleAuth: jest.fn(),
  fetchCurrentUser: jest.fn(),
  logout: jest.fn(),
}));

import { useAuth } from '../hooks/useAuth';
import { getAccessToken, getUser } from '../services/storage';
import { startGoogleAuth, fetchCurrentUser, logout } from '../services/auth';

const mockGetToken = getAccessToken as jest.MockedFunction<typeof getAccessToken>;
const mockGetUser = getUser as jest.MockedFunction<typeof getUser>;
const mockStartAuth = startGoogleAuth as jest.MockedFunction<typeof startGoogleAuth>;
const mockFetchUser = fetchCurrentUser as jest.MockedFunction<typeof fetchCurrentUser>;
const mockLogout = logout as jest.MockedFunction<typeof logout>;

beforeEach(() => {
  jest.clearAllMocks();
});

describe('useAuth', () => {
  it('initializes as loading', () => {
    mockGetToken.mockResolvedValue(null);
    const { result } = renderHook(() => useAuth());
    expect(result.current.isLoading).toBe(true);
    expect(result.current.isAuthenticated).toBe(false);
  });

  it('sets isAuthenticated when token exists', async () => {
    const user = { id: '1', email: 'test@test.com', name: 'Test' };
    mockGetToken.mockResolvedValue('valid-token');
    mockGetUser.mockResolvedValue(user);

    const { result } = renderHook(() => useAuth());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.user).toEqual(user);
  });

  it('sets unauthenticated when no token', async () => {
    mockGetToken.mockResolvedValue(null);

    const { result } = renderHook(() => useAuth());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.user).toBeNull();
  });

  it('signOut clears state', async () => {
    mockGetToken.mockResolvedValue('token');
    mockGetUser.mockResolvedValue({ id: '1', email: 'a@b.com', name: 'A' });
    mockLogout.mockResolvedValue(undefined);

    const { result } = renderHook(() => useAuth());

    await waitFor(() => {
      expect(result.current.isAuthenticated).toBe(true);
    });

    await act(async () => {
      await result.current.signOut();
    });

    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.user).toBeNull();
    expect(mockLogout).toHaveBeenCalled();
  });

  it('handles sign in error gracefully', async () => {
    mockGetToken.mockResolvedValue(null);
    mockStartAuth.mockRejectedValue(new Error('Network error'));

    const { result } = renderHook(() => useAuth());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await act(async () => {
      await result.current.signIn();
    });

    expect(result.current.error).toBe('Network error');
    expect(result.current.isAuthenticated).toBe(false);
  });
});
