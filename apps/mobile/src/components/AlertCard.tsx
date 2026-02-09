/** Alert card component for the inbox. */

import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';

import type { Alert } from '../types';
import { URGENCY_COLORS } from '../utils/constants';

interface AlertCardProps {
  alert: Alert;
  onPress: (alert: Alert) => void;
}

export function AlertCard({ alert, onPress }: AlertCardProps) {
  return (
    <TouchableOpacity
      style={[styles.card, !alert.read && styles.unread]}
      onPress={() => onPress(alert)}
      activeOpacity={0.7}
    >
      <View style={styles.header}>
        <Text style={styles.from} numberOfLines={1}>
          {alert.from_addr ?? 'Unknown sender'}
        </Text>
        <Text style={styles.time}>
          {new Date(alert.created_at).toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
          })}
        </Text>
      </View>

      <Text style={styles.subject} numberOfLines={1}>
        {alert.subject ?? '(no subject)'}
      </Text>

      <Text style={styles.snippet} numberOfLines={2}>
        {alert.snippet ?? ''}
      </Text>

      {alert.rule_name && (
        <View style={styles.ruleTag}>
          <Text style={styles.ruleTagText}>{alert.rule_name}</Text>
        </View>
      )}

      {!alert.read && <View style={styles.unreadDot} />}
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
  },
  unread: {
    backgroundColor: '#f0f4ff',
    borderLeftWidth: 3,
    borderLeftColor: '#4A90D9',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  from: {
    fontSize: 15,
    fontWeight: '600',
    color: '#1a1a2e',
    flex: 1,
  },
  time: {
    fontSize: 12,
    color: '#888',
    marginLeft: 8,
  },
  subject: {
    fontSize: 14,
    fontWeight: '500',
    color: '#333',
    marginBottom: 4,
  },
  snippet: {
    fontSize: 13,
    color: '#666',
    lineHeight: 18,
  },
  ruleTag: {
    backgroundColor: '#e8eaf6',
    borderRadius: 4,
    paddingHorizontal: 8,
    paddingVertical: 2,
    alignSelf: 'flex-start',
    marginTop: 8,
  },
  ruleTagText: {
    fontSize: 11,
    color: '#3f51b5',
    fontWeight: '500',
  },
  unreadDot: {
    position: 'absolute',
    top: 16,
    right: 16,
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#4A90D9',
  },
});
