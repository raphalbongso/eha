/** Push notification registration and local notifications. */

import * as Device from 'expo-device';
import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';

import type { DeviceRegisterRequest } from '../types';
import api from './api';

// Configure notification behavior
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
  }),
});

export async function registerForPushNotifications(): Promise<string | null> {
  if (!Device.isDevice) {
    console.warn('Push notifications require a physical device');
    return null;
  }

  // Check existing permissions
  const { status: existingStatus } =
    await Notifications.getPermissionsAsync();
  let finalStatus = existingStatus;

  if (existingStatus !== 'granted') {
    const { status } = await Notifications.requestPermissionsAsync();
    finalStatus = status;
  }

  if (finalStatus !== 'granted') {
    console.warn('Push notification permission not granted');
    return null;
  }

  // Get push token
  const tokenResult = await Notifications.getExpoPushTokenAsync();
  const pushToken = tokenResult.data;

  // Register with backend
  const deviceId = Device.modelId || Device.deviceName || 'unknown';
  const platform: DeviceRegisterRequest['platform'] =
    Platform.OS === 'ios' ? 'ios' : 'android';

  try {
    await api.post('/devices/register', {
      platform,
      token: pushToken,
      device_id: deviceId,
    } satisfies DeviceRegisterRequest);
  } catch (error) {
    console.error('Failed to register device token:', error);
  }

  return pushToken;
}

export function addNotificationReceivedListener(
  handler: (notification: Notifications.Notification) => void,
): Notifications.Subscription {
  return Notifications.addNotificationReceivedListener(handler);
}

export function addNotificationResponseListener(
  handler: (response: Notifications.NotificationResponse) => void,
): Notifications.Subscription {
  return Notifications.addNotificationResponseReceivedListener(handler);
}

export async function scheduleLocalNotification(
  title: string,
  body: string,
  triggerSeconds: number,
): Promise<string> {
  return Notifications.scheduleNotificationAsync({
    content: { title, body },
    trigger: { seconds: triggerSeconds },
  });
}
