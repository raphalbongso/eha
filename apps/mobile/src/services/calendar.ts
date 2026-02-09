/** Native calendar integration using react-native-calendar-events. */

import RNCalendarEvents, {
  CalendarEventWritable,
} from 'react-native-calendar-events';
import { Platform, Alert as RNAlert } from 'react-native';

import { DEFAULT_REMINDER_MINUTES } from '../utils/constants';
import type { EventData } from '../types';

export async function requestCalendarPermission(): Promise<boolean> {
  const status = await RNCalendarEvents.requestPermissions();
  return status === 'authorized';
}

export async function checkCalendarPermission(): Promise<boolean> {
  const status = await RNCalendarEvents.checkPermissions();
  return status === 'authorized';
}

export async function addEventToCalendar(
  eventData: EventData,
  reminderMinutes: readonly number[] = DEFAULT_REMINDER_MINUTES,
): Promise<string | null> {
  const hasPermission = await requestCalendarPermission();
  if (!hasPermission) {
    RNAlert.alert(
      'Calendar Permission',
      'EHA needs calendar access to add this event. Please enable it in Settings.',
    );
    return null;
  }

  if (!eventData.title || !eventData.start_datetime) {
    RNAlert.alert('Missing Data', 'Event title and start time are required.');
    return null;
  }

  const startDate = new Date(eventData.start_datetime);
  let endDate: Date;

  if (eventData.end_datetime) {
    endDate = new Date(eventData.end_datetime);
  } else if (eventData.duration_minutes) {
    endDate = new Date(
      startDate.getTime() + eventData.duration_minutes * 60000,
    );
  } else {
    // Default to 1 hour
    endDate = new Date(startDate.getTime() + 60 * 60000);
  }

  const calendarEvent: CalendarEventWritable = {
    startDate: startDate.toISOString(),
    endDate: endDate.toISOString(),
    location: eventData.location ?? undefined,
    alarms: reminderMinutes.map((minutes) => ({
      date: -minutes, // Negative = before event
    })),
  };

  try {
    const eventId = await RNCalendarEvents.saveEvent(
      eventData.title,
      calendarEvent,
    );
    return eventId;
  } catch (error) {
    console.error('Failed to add event to calendar:', error);
    RNAlert.alert('Error', 'Failed to add event to calendar. Please try again.');
    return null;
  }
}
