/** Inbox screen showing alerts and matched emails. */

import React, { useCallback } from 'react';
import {
  ActivityIndicator,
  FlatList,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import type { Alert, RootStackParamList } from '../types';
import { AlertCard } from '../components/AlertCard';
import { useAlerts } from '../hooks/useAlerts';

type NavProp = NativeStackNavigationProp<RootStackParamList>;

export function InboxScreen() {
  const navigation = useNavigation<NavProp>();
  const { alerts, isLoading, fetchAlerts, markAsRead, unreadCount } =
    useAlerts();

  const handleAlertPress = useCallback(
    (alert: Alert) => {
      if (!alert.read) {
        markAsRead([alert.id]);
      }
      navigation.navigate('EmailDetail', {
        messageId: alert.message_id,
        subject: alert.subject ?? undefined,
        fromAddr: alert.from_addr ?? undefined,
      });
    },
    [navigation, markAsRead],
  );

  const renderItem = ({ item }: { item: Alert }) => (
    <AlertCard alert={item} onPress={handleAlertPress} />
  );

  return (
    <View style={styles.container}>
      {unreadCount > 0 && (
        <View style={styles.badge}>
          <Text style={styles.badgeText}>{unreadCount} unread</Text>
        </View>
      )}

      <FlatList
        data={alerts}
        keyExtractor={(item) => item.id}
        renderItem={renderItem}
        refreshControl={
          <RefreshControl refreshing={isLoading} onRefresh={fetchAlerts} />
        }
        ListEmptyComponent={
          !isLoading ? (
            <View style={styles.empty}>
              <Text style={styles.emptyTitle}>No alerts yet</Text>
              <Text style={styles.emptyText}>
                Set up rules in the Rules tab to start getting smart
                notifications.
              </Text>
            </View>
          ) : null
        }
        contentContainerStyle={alerts.length === 0 ? styles.emptyList : undefined}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  badge: {
    backgroundColor: '#4A90D9',
    paddingHorizontal: 12,
    paddingVertical: 6,
    marginHorizontal: 16,
    marginTop: 8,
    borderRadius: 16,
    alignSelf: 'flex-start',
  },
  badgeText: {
    color: '#fff',
    fontSize: 12,
    fontWeight: '600',
  },
  empty: {
    alignItems: 'center',
    paddingHorizontal: 32,
  },
  emptyTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#333',
    marginBottom: 8,
  },
  emptyText: {
    fontSize: 14,
    color: '#888',
    textAlign: 'center',
    lineHeight: 20,
  },
  emptyList: {
    flex: 1,
    justifyContent: 'center',
  },
});
