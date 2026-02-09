/** Settings screen with account info, travel preferences (v2), and data management. */

import React, { useCallback, useEffect, useState } from 'react';
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

import { useAuth } from '../hooks/useAuth';
import api from '../services/api';

type TransportMode = 'driving' | 'transit' | 'cycling' | 'walking';

interface Preferences {
  home_address: string | null;
  work_address: string | null;
  preferred_transport_mode: TransportMode | null;
}

export function SettingsScreen() {
  const { user, signOut } = useAuth();

  const [homeAddress, setHomeAddress] = useState('');
  const [workAddress, setWorkAddress] = useState('');
  const [transportMode, setTransportMode] = useState<TransportMode>('driving');
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  // Fetch existing preferences on mount
  useEffect(() => {
    const fetchPreferences = async () => {
      setIsLoading(true);
      try {
        const { data } = await api.get<Preferences>('/preferences');
        setHomeAddress(data.home_address ?? '');
        setWorkAddress(data.work_address ?? '');
        setTransportMode(data.preferred_transport_mode ?? 'driving');
      } catch {
        // Preferences not yet set — use defaults
      } finally {
        setIsLoading(false);
      }
    };
    fetchPreferences();
  }, []);

  const savePreferences = useCallback(async () => {
    setIsSaving(true);
    try {
      await api.put('/preferences', {
        home_address: homeAddress || null,
        work_address: workAddress || null,
        preferred_transport_mode: transportMode,
      });
      RNAlert.alert('Saved', 'Your travel preferences have been updated.');
    } catch {
      RNAlert.alert('Error', 'Failed to save preferences. Please try again.');
    } finally {
      setIsSaving(false);
    }
  }, [homeAddress, workAddress, transportMode]);

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
            } catch {
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

      {/* Travel Preferences (v2 — now enabled) */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Travel Preferences</Text>
        {isLoading ? (
          <ActivityIndicator style={{ marginVertical: 20 }} />
        ) : (
          <View style={styles.card}>
            <Text style={styles.label}>Home Address</Text>
            <TextInput
              style={styles.input}
              value={homeAddress}
              onChangeText={setHomeAddress}
              placeholder="Your home address"
              placeholderTextColor="#aaa"
            />
            <Text style={styles.label}>Work Address</Text>
            <TextInput
              style={styles.input}
              value={workAddress}
              onChangeText={setWorkAddress}
              placeholder="Your work address"
              placeholderTextColor="#aaa"
            />
            <Text style={styles.label}>Preferred Transport</Text>
            <View style={styles.transportRow}>
              {(['driving', 'transit', 'cycling', 'walking'] as TransportMode[]).map(
                (mode) => (
                  <TouchableOpacity
                    key={mode}
                    style={[
                      styles.transportChip,
                      transportMode === mode && styles.transportActive,
                    ]}
                    onPress={() => setTransportMode(mode)}
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
                ),
              )}
            </View>
            <TouchableOpacity
              style={[styles.saveBtn, isSaving && styles.saveBtnDisabled]}
              onPress={savePreferences}
              disabled={isSaving}
            >
              <Text style={styles.saveBtnText}>
                {isSaving ? 'Saving...' : 'Save Preferences'}
              </Text>
            </TouchableOpacity>
          </View>
        )}
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

      <Text style={styles.version}>EHA v2.0.0</Text>
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
    color: '#333',
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
  saveBtn: {
    marginTop: 16,
    padding: 12,
    borderRadius: 8,
    backgroundColor: '#4A90D9',
    alignItems: 'center',
  },
  saveBtnDisabled: { opacity: 0.6 },
  saveBtnText: { color: '#fff', fontWeight: '600', fontSize: 14 },
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
