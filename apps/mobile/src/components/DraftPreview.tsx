/** Draft preview component for AI-generated reply options. */

import React from 'react';
import {
  Alert as RNAlert,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';

import type { DraftProposal } from '../types';
import { TONE_LABELS } from '../utils/constants';

interface DraftPreviewProps {
  draft: DraftProposal;
  onSelect: (draft: DraftProposal) => void;
  isSelected?: boolean;
}

export function DraftPreview({ draft, onSelect, isSelected }: DraftPreviewProps) {
  return (
    <TouchableOpacity
      style={[styles.card, isSelected && styles.selected]}
      onPress={() => onSelect(draft)}
      activeOpacity={0.7}
    >
      <View style={styles.header}>
        <View style={[styles.toneBadge, styles[`tone_${draft.tone}`]]}>
          <Text style={styles.toneText}>
            {TONE_LABELS[draft.tone] ?? draft.tone}
          </Text>
        </View>
      </View>

      <Text style={styles.subject} numberOfLines={1}>
        {draft.subject}
      </Text>

      <Text style={styles.body} numberOfLines={4}>
        {draft.body}
      </Text>

      <Text style={styles.disclaimer}>
        Draft only — will NOT be sent automatically
      </Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 16,
    marginVertical: 6,
    borderWidth: 1,
    borderColor: '#e0e0e0',
  },
  selected: {
    borderColor: '#4A90D9',
    borderWidth: 2,
    backgroundColor: '#f5f8ff',
  },
  header: {
    flexDirection: 'row',
    marginBottom: 8,
  },
  toneBadge: {
    borderRadius: 12,
    paddingHorizontal: 10,
    paddingVertical: 3,
  },
  tone_formal: {
    backgroundColor: '#e3f2fd',
  },
  tone_friendly: {
    backgroundColor: '#e8f5e9',
  },
  tone_brief: {
    backgroundColor: '#fff3e0',
  },
  toneText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#333',
  },
  subject: {
    fontSize: 14,
    fontWeight: '500',
    color: '#333',
    marginBottom: 6,
  },
  body: {
    fontSize: 13,
    color: '#555',
    lineHeight: 19,
  },
  disclaimer: {
    fontSize: 11,
    color: '#999',
    marginTop: 8,
    fontStyle: 'italic',
  },
});
