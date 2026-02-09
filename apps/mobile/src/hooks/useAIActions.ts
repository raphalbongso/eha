/** Hook for AI actions: summarize, generate drafts, extract events. */

import { useCallback, useState } from 'react';

import type { DraftProposal, ProposedEvent, Summary } from '../types';
import api from '../services/api';

interface AIActionsState {
  summary: Summary | null;
  drafts: DraftProposal[];
  proposedEvent: ProposedEvent | null;
  isLoading: boolean;
  error: string | null;
}

export function useAIActions() {
  const [state, setState] = useState<AIActionsState>({
    summary: null,
    drafts: [],
    proposedEvent: null,
    isLoading: false,
    error: null,
  });

  const summarize = useCallback(async (messageId: string) => {
    setState((prev) => ({ ...prev, isLoading: true, error: null }));
    try {
      const { data } = await api.post<Summary>('/ai/summarize', {
        message_id: messageId,
      });
      setState((prev) => ({
        ...prev,
        summary: data,
        isLoading: false,
      }));
      return data;
    } catch (error) {
      setState((prev) => ({
        ...prev,
        isLoading: false,
        error: 'Failed to summarize email',
      }));
      return null;
    }
  }, []);

  const generateDrafts = useCallback(
    async (messageId: string, userContext: string = '', numDrafts: number = 3) => {
      setState((prev) => ({ ...prev, isLoading: true, error: null }));
      try {
        const { data } = await api.post<DraftProposal[]>('/ai/drafts', {
          message_id: messageId,
          user_context: userContext,
          num_drafts: numDrafts,
        });
        setState((prev) => ({
          ...prev,
          drafts: data,
          isLoading: false,
        }));
        return data;
      } catch (error) {
        setState((prev) => ({
          ...prev,
          isLoading: false,
          error: 'Failed to generate drafts',
        }));
        return [];
      }
    },
    [],
  );

  const extractEvent = useCallback(async (messageId: string) => {
    setState((prev) => ({ ...prev, isLoading: true, error: null }));
    try {
      const { data } = await api.post<ProposedEvent | null>(
        '/ai/extract-event',
        { message_id: messageId },
      );
      setState((prev) => ({
        ...prev,
        proposedEvent: data,
        isLoading: false,
      }));
      return data;
    } catch (error) {
      setState((prev) => ({
        ...prev,
        isLoading: false,
        error: 'Failed to extract event',
      }));
      return null;
    }
  }, []);

  const createDraft = useCallback(
    async (params: {
      messageId: string;
      to: string;
      subject: string;
      body: string;
      tone: string;
      threadId?: string;
    }) => {
      try {
        const { data } = await api.post('/drafts', {
          message_id: params.messageId,
          to: params.to,
          subject: params.subject,
          body: params.body,
          tone: params.tone,
          thread_id: params.threadId,
        });
        return data;
      } catch (error) {
        console.error('Failed to create draft:', error);
        return null;
      }
    },
    [],
  );

  const clearState = useCallback(() => {
    setState({
      summary: null,
      drafts: [],
      proposedEvent: null,
      isLoading: false,
      error: null,
    });
  }, []);

  return {
    ...state,
    summarize,
    generateDrafts,
    extractEvent,
    createDraft,
    clearState,
  };
}
