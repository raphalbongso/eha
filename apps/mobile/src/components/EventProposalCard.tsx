/** Event proposal card component. */

import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';

import type { ProposedEvent } from '../types';

interface EventProposalCardProps {
  event: ProposedEvent;
  onPress: (event: ProposedEvent) => void;
}

export function EventProposalCard({ event, onPress }: EventProposalCardProps) {
  const { event_data } = event;
  const confidence = event_data.confidence;
  const isLowConfidence = confidence < 0.5;

  const formatDateTime = (iso: string | null): string => {
    if (!iso) return 'Not specified';
    try {
      return new Date(iso).toLocaleString([], {
        dateStyle: 'medium',
        timeStyle: 'short',
      });
    } catch {
      return iso;
    }
  };

  return (
    <TouchableOpacity
      style={styles.card}
      onPress={() => onPress(event)}
      activeOpacity={0.7}
    >
      <View style={styles.header}>
        <Text style={styles.title} numberOfLines={2}>
          {event_data.title ?? 'Untitled Event'}
        </Text>
        <View
          style={[
            styles.confidenceBadge,
            isLowConfidence ? styles.lowConfidence : styles.highConfidence,
          ]}
        >
          <Text style={styles.confidenceText}>
            {Math.round(confidence * 100)}%
          </Text>
        </View>
      </View>

      <View style={styles.detail}>
        <Text style={styles.label}>When</Text>
        <Text style={styles.value}>
          {formatDateTime(event_data.start_datetime)}
        </Text>
      </View>

      {event_data.location && (
        <View style={styles.detail}>
          <Text style={styles.label}>Where</Text>
          <Text style={styles.value}>{event_data.location}</Text>
        </View>
      )}

      {event_data.attendees && event_data.attendees.length > 0 && (
        <View style={styles.detail}>
          <Text style={styles.label}>With</Text>
          <Text style={styles.value} numberOfLines={1}>
            {event_data.attendees.join(', ')}
          </Text>
        </View>
      )}

      {isLowConfidence && (
        <Text style={styles.warning}>
          Low confidence — please review carefully before confirming
        </Text>
      )}

      <View style={styles.statusRow}>
        <Text style={styles.statusText}>
          {event.status === 'proposed' ? 'Tap to review & confirm' : event.status}
        </Text>
      </View>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 16,
    marginHorizontal: 16,
    marginVertical: 6,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 3,
    elevation: 2,
    borderLeftWidth: 3,
    borderLeftColor: '#7C4DFF',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 12,
  },
  title: {
    fontSize: 16,
    fontWeight: '600',
    color: '#1a1a2e',
    flex: 1,
    marginRight: 8,
  },
  confidenceBadge: {
    borderRadius: 10,
    paddingHorizontal: 8,
    paddingVertical: 2,
  },
  highConfidence: {
    backgroundColor: '#e8f5e9',
  },
  lowConfidence: {
    backgroundColor: '#fff3e0',
  },
  confidenceText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#333',
  },
  detail: {
    flexDirection: 'row',
    marginBottom: 4,
  },
  label: {
    fontSize: 13,
    color: '#888',
    width: 50,
  },
  value: {
    fontSize: 13,
    color: '#333',
    flex: 1,
  },
  warning: {
    fontSize: 12,
    color: '#e65100',
    marginTop: 8,
    fontStyle: 'italic',
  },
  statusRow: {
    marginTop: 10,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: '#eee',
  },
  statusText: {
    fontSize: 13,
    color: '#7C4DFF',
    fontWeight: '500',
    textAlign: 'center',
  },
});
