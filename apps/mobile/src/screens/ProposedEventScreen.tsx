/** Proposed event screen — review, edit, and confirm event to device calendar. */

import React, { useState } from 'react';
import {
  Alert as RNAlert,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import type { EventData, RootStackParamList } from '../types';
import { addEventToCalendar } from '../services/calendar';
import api from '../services/api';

type ScreenProps = NativeStackScreenProps<RootStackParamList, 'ProposedEvent'>;

export function ProposedEventScreen() {
  const route = useRoute<ScreenProps['route']>();
  const navigation = useNavigation();
  const { event } = route.params;

  const [title, setTitle] = useState(event.event_data.title ?? '');
  const [startDatetime, setStartDatetime] = useState(
    event.event_data.start_datetime ?? '',
  );
  const [endDatetime, setEndDatetime] = useState(
    event.event_data.end_datetime ?? '',
  );
  const [location, setLocation] = useState(event.event_data.location ?? '');
  const [isSaving, setIsSaving] = useState(false);

  const confidence = event.event_data.confidence;

  const handleConfirm = async () => {
    if (!title.trim() || !startDatetime.trim()) {
      RNAlert.alert('Missing Data', 'Title and start time are required.');
      return;
    }

    setIsSaving(true);
    try {
      // 1. Confirm on backend
      await api.post('/events/confirm', { event_id: event.id });

      // 2. Write to device calendar
      const eventData: EventData = {
        title: title.trim(),
        start_datetime: startDatetime,
        end_datetime: endDatetime || null,
        duration_minutes: event.event_data.duration_minutes,
        location: location || null,
        attendees: event.event_data.attendees,
        confidence,
      };

      const calendarEventId = await addEventToCalendar(eventData);

      if (calendarEventId) {
        RNAlert.alert(
          'Event Added',
          'The event has been added to your calendar with reminders (60 min and 15 min before).',
          [{ text: 'OK', onPress: () => navigation.goBack() }],
        );
      }
    } catch (error) {
      RNAlert.alert('Error', 'Failed to confirm event. Please try again.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleDismiss = async () => {
    RNAlert.alert('Dismiss Event', 'Are you sure you want to dismiss this event?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Dismiss',
        style: 'destructive',
        onPress: async () => {
          try {
            await api.post('/events/dismiss', { event_id: event.id });
            navigation.goBack();
          } catch (error) {
            RNAlert.alert('Error', 'Failed to dismiss event.');
          }
        },
      },
    ]);
  };

  return (
    <ScrollView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Review Event</Text>
        <View
          style={[
            styles.confidenceBadge,
            confidence < 0.5 ? styles.lowConf : styles.highConf,
          ]}
        >
          <Text style={styles.confidenceText}>
            {Math.round(confidence * 100)}% confidence
          </Text>
        </View>
      </View>

      {confidence < 0.5 && (
        <View style={styles.warning}>
          <Text style={styles.warningText}>
            Low confidence detection. Please review all fields carefully before
            confirming.
          </Text>
        </View>
      )}

      <View style={styles.field}>
        <Text style={styles.label}>Title</Text>
        <TextInput
          style={styles.input}
          value={title}
          onChangeText={setTitle}
          placeholder="Event title"
        />
      </View>

      <View style={styles.field}>
        <Text style={styles.label}>Start Date/Time</Text>
        <TextInput
          style={styles.input}
          value={startDatetime}
          onChangeText={setStartDatetime}
          placeholder="YYYY-MM-DDTHH:mm:ss"
        />
      </View>

      <View style={styles.field}>
        <Text style={styles.label}>End Date/Time</Text>
        <TextInput
          style={styles.input}
          value={endDatetime}
          onChangeText={setEndDatetime}
          placeholder="YYYY-MM-DDTHH:mm:ss (optional)"
        />
      </View>

      <View style={styles.field}>
        <Text style={styles.label}>Location</Text>
        <TextInput
          style={styles.input}
          value={location}
          onChangeText={setLocation}
          placeholder="Location (optional)"
        />
      </View>

      {event.event_data.attendees && event.event_data.attendees.length > 0 && (
        <View style={styles.field}>
          <Text style={styles.label}>Attendees</Text>
          <Text style={styles.attendees}>
            {event.event_data.attendees.join(', ')}
          </Text>
        </View>
      )}

      <Text style={styles.reminderNote}>
        Reminders will be set: 60 min and 15 min before the event.
      </Text>

      <View style={styles.actions}>
        <TouchableOpacity style={styles.dismissBtn} onPress={handleDismiss}>
          <Text style={styles.dismissBtnText}>Dismiss</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.confirmBtn}
          onPress={handleConfirm}
          disabled={isSaving}
        >
          <Text style={styles.confirmBtnText}>
            {isSaving ? 'Adding...' : 'Add to Calendar'}
          </Text>
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  header: {
    padding: 16,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderBottomWidth: 1,
    borderBottomColor: '#eee',
  },
  headerTitle: { fontSize: 20, fontWeight: '700', color: '#1a1a2e' },
  confidenceBadge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12 },
  highConf: { backgroundColor: '#e8f5e9' },
  lowConf: { backgroundColor: '#fff3e0' },
  confidenceText: { fontSize: 12, fontWeight: '600', color: '#333' },
  warning: {
    backgroundColor: '#fff3e0',
    padding: 12,
    marginHorizontal: 16,
    marginTop: 12,
    borderRadius: 8,
  },
  warningText: { fontSize: 13, color: '#e65100', lineHeight: 18 },
  field: { paddingHorizontal: 16, paddingTop: 16 },
  label: { fontSize: 13, fontWeight: '600', color: '#666', marginBottom: 6 },
  input: {
    backgroundColor: '#f5f5f5',
    borderRadius: 8,
    padding: 12,
    fontSize: 15,
    borderWidth: 1,
    borderColor: '#e0e0e0',
  },
  attendees: { fontSize: 14, color: '#444', lineHeight: 20 },
  reminderNote: {
    fontSize: 12,
    color: '#888',
    textAlign: 'center',
    marginTop: 20,
    paddingHorizontal: 16,
  },
  actions: {
    flexDirection: 'row',
    padding: 16,
    gap: 12,
    marginTop: 16,
    marginBottom: 40,
  },
  dismissBtn: {
    flex: 1,
    padding: 14,
    borderRadius: 10,
    backgroundColor: '#f5f5f5',
    alignItems: 'center',
  },
  dismissBtnText: { color: '#f44336', fontWeight: '600', fontSize: 15 },
  confirmBtn: {
    flex: 2,
    padding: 14,
    borderRadius: 10,
    backgroundColor: '#7C4DFF',
    alignItems: 'center',
  },
  confirmBtnText: { color: '#fff', fontWeight: '600', fontSize: 15 },
});
