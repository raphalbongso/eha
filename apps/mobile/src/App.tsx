/** EHA — Email Helper Agent: App entry point. */

import React, { useEffect } from 'react';
import { StatusBar } from 'react-native';

import { AppNavigator } from './navigation/AppNavigator';
import { registerForPushNotifications, addNotificationResponseListener } from './services/notifications';

export default function App() {
  useEffect(() => {
    // Register for push notifications on mount
    registerForPushNotifications();

    // Handle notification taps
    const subscription = addNotificationResponseListener((response) => {
      const data = response.notification.request.content.data;
      // Navigation to specific screen based on notification type
      // is handled by the navigation container's linking config
      console.log('Notification tapped:', data);
    });

    return () => subscription.remove();
  }, []);

  return (
    <>
      <StatusBar barStyle="light-content" backgroundColor="#1a1a2e" />
      <AppNavigator />
    </>
  );
}
