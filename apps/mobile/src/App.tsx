/** EHA — Email Helper Agent: App entry point. */

import React, { useEffect } from 'react';
import { StatusBar } from 'react-native';
import * as Sentry from '@sentry/react-native';
import Constants from 'expo-constants';

import { AppNavigator, navigationRef } from './navigation/AppNavigator';
import { registerForPushNotifications, addNotificationResponseListener } from './services/notifications';
import { registerBackgroundFetch } from './services/backgroundAlerts';

const sentryDsn = Constants.expoConfig?.extra?.sentryDsn as string | null;
if (sentryDsn) {
  Sentry.init({
    dsn: sentryDsn,
    tracesSampleRate: 0.1,
    sendDefaultPii: false,
  });
}

function App() {
  useEffect(() => {
    // Register for push notifications and background fetch on mount
    registerForPushNotifications();
    registerBackgroundFetch();

    // Handle notification taps — navigate to EmailDetail when applicable
    const subscription = addNotificationResponseListener((response) => {
      const data = response.notification.request.content.data as Record<string, string>;
      if (data?.alert_id && data?.message_subject && navigationRef.isReady()) {
        navigationRef.navigate('EmailDetail', {
          messageId: data.alert_id,
          subject: data.message_subject,
        });
      }
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

export default Sentry.wrap(App);
