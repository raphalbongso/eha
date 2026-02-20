/** iOS background app refresh: fetch unread alert count and update badge. */

import * as BackgroundFetch from 'expo-background-fetch';
import * as TaskManager from 'expo-task-manager';
import * as Notifications from 'expo-notifications';

import api from './api';

const TASK_NAME = 'EHA_BACKGROUND_ALERT_CHECK';

// Must be defined at module scope for TaskManager
TaskManager.defineTask(TASK_NAME, async () => {
  try {
    const { data } = await api.get<{ unread_count: number }>('/alerts/count');
    await Notifications.setBadgeCountAsync(data.unread_count);
    return data.unread_count > 0
      ? BackgroundFetch.BackgroundFetchResult.NewData
      : BackgroundFetch.BackgroundFetchResult.NoData;
  } catch {
    return BackgroundFetch.BackgroundFetchResult.Failed;
  }
});

export async function registerBackgroundFetch(): Promise<void> {
  const status = await BackgroundFetch.getStatusAsync();
  if (status === BackgroundFetch.BackgroundFetchStatus.Denied) {
    return;
  }

  const isRegistered = await TaskManager.isTaskRegisteredAsync(TASK_NAME);
  if (!isRegistered) {
    await BackgroundFetch.registerTaskAsync(TASK_NAME, {
      minimumInterval: 15 * 60, // 15 minutes
      stopOnTerminate: false,
      startOnBoot: true,
    });
  }
}
