/** Settings screen with account info, preferences, and v2 hooks. */

import React, { useEffect, useState } from 'react';
import {
  Alert as RNAlert,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';

import { useAuth } from '../hooks/useAuth';
import api from '../services/api';

export function SettingsScreen() {
  const { user, signOut } = useAuth();

  // v2 placeholders for travel preferences
  const [homeAddress, setHomeAddress] = useState('');
  const [workAddress, setWorkAddress] = useState('');
  const [transportMode, setTransportMode] = useState('driving');

  const handleDeleteAccount = () => {
    RNAlert.alert(
      'Delete All Data',
      'This will permanently delete your account and all associated data (rules, alerts, drafts, events). This cannot be undone.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete Everything',
          style: 'destructive',
          onPress: async () => {
            try {
              await api.delete('/users/me/data');
              await signOut();
            } catch (error) {
              RNAlert.alert('Error', 'Failed to delete data. Please try again.');
            }
          },
        },
      ],
    );
  };

  return (
    <ScrollView style={styles.container}>
      {/* Account */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Account</Text>
        <View style={styles.card}>
          <Text style={styles.label}>Name</Text>
          <Text style={styles.value}>{user?.name ?? '—'}</Text>
          <Text style={styles.label}>Email</Text>
          <Text style={styles.value}>{user?.email ?? '—'}</Text>
        </View>
      </View>

      {/* Travel Preferences (v2 placeholder) */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Travel Preferences</Text>
        <Text style={styles.comingSoon}>Coming in v2 — route-based leave reminders</Text>
        <View style={styles.card}>
          <Text style={styles.label}>Home Address</Text>
          <TextInput
            style={styles.input}
            value={homeAddress}
            onChangeText={setHomeAddress}
            placeholder="Your home address"
            editable={false}
          />
          <Text style={styles.label}>Work Address</Text>
          <TextInput
            style={styles.input}
            value={workAddress}
            onChangeText={setWorkAddress}
            placeholder="Your work address"
            editable={false}
          />
          <Text style={styles.label}>Preferred Transport</Text>
          <View style={styles.transportRow}>
            {['driving', 'transit', 'cycling', 'walking'].map((mode) => (
              <TouchableOpacity
                key={mode}
                style={[
                  styles.transportChip,
                  transportMode === mode && styles.transportActive,
                ]}
                onPress={() => setTransportMode(mode)}
                disabled
              >
                <Text
                  style={
                    transportMode === mode
                      ? styles.transportActiveText
                      : styles.transportText
                  }
                >
                  {mode}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>
      </View>

      {/* Privacy */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Privacy & Data</Text>
        <View style={styles.card}>
          <Text style={styles.privacyNote}>
            EHA never sends emails automatically. Email body content is only
            processed transiently by AI and never stored permanently. All tokens
            are encrypted at rest.
          </Text>
          <TouchableOpacity
            style={styles.deleteBtn}
            onPress={handleDeleteAccount}
          >
            <Text style={styles.deleteBtnText}>Delete All My Data</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Sign Out */}
      <TouchableOpacity style={styles.signOutBtn} onPress={signOut}>
        <Text style={styles.signOutText}>Sign Out</Text>
      </TouchableOpacity>

      <Text style={styles.version}>EHA v1.0.0</Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f5f5f5' },
  section: { marginTop: 20 },
  sectionTitle: {
    fontSize: 13,
    fontWeight: '600',
    color: '#888',
    textTransform: 'uppercase',
    paddingHorizontal: 16,
    marginBottom: 8,
  },
  comingSoon: {
    fontSize: 11,
    color: '#aaa',
    paddingHorizontal: 16,
    marginBottom: 6,
    fontStyle: 'italic',
  },
  card: {
    backgroundColor: '#fff',
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  label: { fontSize: 12, color: '#888', marginTop: 8 },
  value: { fontSize: 15, color: '#333', marginTop: 2 },
  input: {
    backgroundColor: '#f5f5f5',
    borderRadius: 6,
    padding: 10,
    fontSize: 14,
    marginTop: 4,
    color: '#aaa',
  },
  transportRow: { flexDirection: 'row', gap: 8, marginTop: 8 },
  transportChip: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 14,
    backgroundColor: '#eee',
  },
  transportActive: { backgroundColor: '#4A90D9' },
  transportText: { fontSize: 12, color: '#666' },
  transportActiveText: { fontSize: 12, color: '#fff', fontWeight: '500' },
  privacyNote: {
    fontSize: 13,
    color: '#555',
    lineHeight: 20,
    marginBottom: 16,
  },
  deleteBtn: {
    padding: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#f44336',
    alignItems: 'center',
  },
  deleteBtnText: { color: '#f44336', fontWeight: '600' },
  signOutBtn: {
    margin: 16,
    padding: 14,
    borderRadius: 10,
    backgroundColor: '#fff',
    alignItems: 'center',
  },
  signOutText: { color: '#666', fontWeight: '600', fontSize: 15 },
  version: { textAlign: 'center', color: '#ccc', fontSize: 12, marginBottom: 40 },
});
