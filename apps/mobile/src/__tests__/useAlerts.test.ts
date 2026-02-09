/**
 * Tests for useAlerts hook.
 */

import { renderHook, act, waitFor } from '@testing-library/react-native';

// Mock api module
jest.mock('../services/api', () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
    post: jest.fn(),
  },
}));

import { useAlerts } from '../hooks/useAlerts';
import api from '../services/api';

const mockGet = api.get as jest.MockedFunction<typeof api.get>;
const mockPost = api.post as jest.MockedFunction<typeof api.post>;

const sampleAlerts = [
  {
    id: '1',
    message_id: 'msg_1',
    rule_id: 'rule_1',
    rule_name: 'Boss emails',
    read: false,
    created_at: '2024-02-01T12:00:00Z',
    subject: 'Urgent',
    from_addr: 'boss@company.com',
    snippet: 'Need your input...',
  },
  {
    id: '2',
    message_id: 'msg_2',
    rule_id: null,
    rule_name: null,
    read: true,
    created_at: '2024-02-01T11:00:00Z',
    subject: 'Hello',
    from_addr: 'friend@example.com',
    snippet: 'Just checking in.',
  },
];

beforeEach(() => {
  jest.clearAllMocks();
});

describe('useAlerts', () => {
  it('fetches alerts on mount', async () => {
    mockGet.mockResolvedValue({ data: sampleAlerts } as any);

    const { result } = renderHook(() => useAlerts());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.alerts).toHaveLength(2);
    expect(result.current.unreadCount).toBe(1);
  });

  it('handles fetch error', async () => {
    mockGet.mockRejectedValue(new Error('Network error'));

    const { result } = renderHook(() => useAlerts());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.error).toBe('Failed to load alerts');
    expect(result.current.alerts).toHaveLength(0);
  });

  it('marks alerts as read optimistically', async () => {
    mockGet.mockResolvedValue({ data: sampleAlerts } as any);
    mockPost.mockResolvedValue({ data: { status: 'ok' } } as any);

    const { result } = renderHook(() => useAlerts());

    await waitFor(() => {
      expect(result.current.alerts).toHaveLength(2);
    });

    await act(async () => {
      await result.current.markAsRead(['1']);
    });

    const updatedAlert = result.current.alerts.find((a) => a.id === '1');
    expect(updatedAlert?.read).toBe(true);
    expect(result.current.unreadCount).toBe(0);
  });
});
