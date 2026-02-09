/** Email detail screen with AI actions: summary, drafts, event extraction. */

import React, { useState } from 'react';
import {
  ActivityIndicator,
  Alert as RNAlert,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { NativeStackNavigationProp, NativeStackScreenProps } from '@react-navigation/native-stack';

import type { DraftProposal, RootStackParamList } from '../types';
import { DraftPreview } from '../components/DraftPreview';
import { useAIActions } from '../hooks/useAIActions';
import { URGENCY_COLORS } from '../utils/constants';

type ScreenProps = NativeStackScreenProps<RootStackParamList, 'EmailDetail'>;

export function EmailDetailScreen() {
  const route = useRoute<ScreenProps['route']>();
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { messageId, subject, fromAddr } = route.params;

  const {
    summary,
    drafts,
    proposedEvent,
    isLoading,
    error,
    summarize,
    generateDrafts,
    extractEvent,
    createDraft,
  } = useAIActions();

  const [userContext, setUserContext] = useState('');
  const [selectedDraft, setSelectedDraft] = useState<DraftProposal | null>(null);

  const handleCreateDraft = async (draft: DraftProposal) => {
    if (!fromAddr) {
      RNAlert.alert('Error', 'Cannot create draft without sender address');
      return;
    }

    RNAlert.alert(
      'Create Draft',
      'This will create a draft in your Gmail. You can review and send it yourself.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Create Draft',
          onPress: async () => {
            const result = await createDraft({
              messageId,
              to: fromAddr,
              subject: draft.subject,
              body: draft.body,
              tone: draft.tone,
            });
            if (result) {
              RNAlert.alert('Draft Created', 'Open Gmail to review and send.');
            }
          },
        },
      ],
    );
  };

  const handleExtractEvent = async () => {
    const event = await extractEvent(messageId);
    if (event) {
      navigation.navigate('ProposedEvent', { event });
    } else {
      RNAlert.alert('No Event Found', 'No calendar event was detected in this email.');
    }
  };

  return (
    <ScrollView style={styles.container}>
      <View style={styles.emailHeader}>
        <Text style={styles.subject}>{subject ?? '(no subject)'}</Text>
        <Text style={styles.from}>{fromAddr ?? 'Unknown sender'}</Text>
      </View>

      {/* AI Actions */}
      <View style={styles.actions}>
        <TouchableOpacity
          style={styles.actionBtn}
          onPress={() => summarize(messageId)}
          disabled={isLoading}
        >
          <Text style={styles.actionBtnText}>Summarize</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.actionBtn}
          onPress={() => generateDrafts(messageId, userContext)}
          disabled={isLoading}
        >
          <Text style={styles.actionBtnText}>Generate Replies</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.actionBtn, styles.eventBtn]}
          onPress={handleExtractEvent}
          disabled={isLoading}
        >
          <Text style={styles.actionBtnText}>Find Event</Text>
        </TouchableOpacity>
      </View>

      {isLoading && (
        <ActivityIndicator size="large" color="#4A90D9" style={styles.loader} />
      )}

      {error && <Text style={styles.error}>{error}</Text>}

      {/* Summary */}
      {summary && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Summary</Text>
          <Text style={styles.summaryText}>{summary.summary}</Text>

          <View
            style={[
              styles.urgencyBadge,
              { backgroundColor: URGENCY_COLORS[summary.urgency] + '20' },
            ]}
          >
            <Text
              style={[
                styles.urgencyText,
                { color: URGENCY_COLORS[summary.urgency] },
              ]}
            >
              {summary.urgency.toUpperCase()} priority
            </Text>
          </View>

          {summary.action_items.length > 0 && (
            <View style={styles.actionItems}>
              <Text style={styles.actionItemsTitle}>Action Items:</Text>
              {summary.action_items.map((item, i) => (
                <Text key={i} style={styles.actionItem}>
                  {'\u2022'} {item}
                </Text>
              ))}
            </View>
          )}
        </View>
      )}

      {/* Drafts */}
      {drafts.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Reply Drafts</Text>
          <Text style={styles.disclaimer}>
            Drafts are suggestions only. They will NOT be sent automatically.
          </Text>

          <TextInput
            style={styles.contextInput}
            value={userContext}
            onChangeText={setUserContext}
            placeholder="Add context for better replies (optional)"
            multiline
          />

          {drafts.map((draft, i) => (
            <DraftPreview
              key={i}
              draft={draft}
              onSelect={(d) => {
                setSelectedDraft(d);
                handleCreateDraft(d);
              }}
              isSelected={selectedDraft?.tone === draft.tone}
            />
          ))}
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  emailHeader: {
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#eee',
  },
  subject: { fontSize: 18, fontWeight: '600', color: '#1a1a2e', marginBottom: 4 },
  from: { fontSize: 14, color: '#666' },
  actions: {
    flexDirection: 'row',
    padding: 12,
    gap: 8,
  },
  actionBtn: {
    flex: 1,
    backgroundColor: '#4A90D9',
    borderRadius: 8,
    padding: 10,
    alignItems: 'center',
  },
  eventBtn: {
    backgroundColor: '#7C4DFF',
  },
  actionBtnText: { color: '#fff', fontSize: 13, fontWeight: '600' },
  loader: { marginVertical: 20 },
  error: { color: '#f44336', textAlign: 'center', marginVertical: 8, fontSize: 14 },
  section: {
    padding: 16,
    borderTopWidth: 1,
    borderTopColor: '#eee',
  },
  sectionTitle: { fontSize: 16, fontWeight: '600', color: '#333', marginBottom: 8 },
  summaryText: { fontSize: 14, color: '#444', lineHeight: 22 },
  urgencyBadge: {
    alignSelf: 'flex-start',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
    marginTop: 8,
  },
  urgencyText: { fontSize: 12, fontWeight: '600' },
  actionItems: { marginTop: 12 },
  actionItemsTitle: { fontSize: 14, fontWeight: '600', color: '#333', marginBottom: 4 },
  actionItem: { fontSize: 13, color: '#555', lineHeight: 22, paddingLeft: 8 },
  disclaimer: { fontSize: 12, color: '#999', fontStyle: 'italic', marginBottom: 8 },
  contextInput: {
    backgroundColor: '#f5f5f5',
    borderRadius: 8,
    padding: 10,
    fontSize: 14,
    marginBottom: 12,
    minHeight: 40,
  },
});
