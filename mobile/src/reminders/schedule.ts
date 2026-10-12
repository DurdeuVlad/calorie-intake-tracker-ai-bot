import { Platform } from 'react-native';
import * as Notifications from 'expo-notifications';
import * as SecureStore from 'expo-secure-store';

/**
 * Local daily logging reminder. Everything here is on-device: no server
 * round-trip, no push outbox (server sync is a later phase). The scheduled
 * notification fires even when the app is backgrounded or killed.
 *
 * Prefs live in SecureStore as one small JSON object — unlike the rule list
 * it is a fixed-size blob (~100 bytes), far under the ~2 KB value cap, and
 * SecureStore is the persistence pattern already used for session data.
 */

export interface ReminderPrefs {
  enabled: boolean;
  /** Local time, 0–23 / 0–59. Kept after disable so re-enabling is one tap. */
  hour: number;
  minute: number;
  /** Identifier of the currently scheduled notification, if any. */
  notificationId: string | null;
}

const PREFS_KEY = 'reminders.daily';
const ANDROID_CHANNEL_ID = 'reminders';

const DEFAULT_PREFS: ReminderPrefs = { enabled: false, hour: 19, minute: 0, notificationId: null };

// Foreground presentation — without a handler an app-open reminder is silent.
// Module scope is the documented expo-notifications pattern; the module is
// only imported by the reminders UI, tests, and the scheduler itself.
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldPlaySound: false,
    shouldSetBadge: false,
    shouldShowBanner: true,
    shouldShowList: true,
  }),
});

export async function getReminderPrefs(): Promise<ReminderPrefs> {
  const raw = await SecureStore.getItemAsync(PREFS_KEY);
  if (!raw) return DEFAULT_PREFS;
  try {
    return { ...DEFAULT_PREFS, ...(JSON.parse(raw) as Partial<ReminderPrefs>) };
  } catch {
    return DEFAULT_PREFS;
  }
}

async function savePrefs(prefs: ReminderPrefs): Promise<void> {
  await SecureStore.setItemAsync(PREFS_KEY, JSON.stringify(prefs));
}

/** Android 8+ requires a channel; iOS ignores it. Idempotent. */
async function ensureReminderChannel(): Promise<void> {
  if (Platform.OS !== 'android') return;
  await Notifications.setNotificationChannelAsync(ANDROID_CHANNEL_ID, {
    name: 'Logging reminders',
    importance: Notifications.AndroidImportance.DEFAULT,
  });
}

/**
 * Schedule (or reschedule) the daily reminder at the given local time.
 * Returns true when scheduled; false when notification permission is denied.
 */
export async function scheduleDailyReminder(hour: number, minute: number): Promise<boolean> {
  const existing = await Notifications.getPermissionsAsync();
  const granted = existing.granted || (await Notifications.requestPermissionsAsync()).granted;
  if (!granted) return false;

  await ensureReminderChannel();

  const prefs = await getReminderPrefs();
  if (prefs.notificationId) {
    await Notifications.cancelScheduledNotificationAsync(prefs.notificationId);
  }

  const notificationId = await Notifications.scheduleNotificationAsync({
    content: {
      title: 'Time to log',
      body: "Don't forget to log what you ate today.",
    },
    trigger: {
      type: Notifications.SchedulableTriggerInputTypes.DAILY,
      hour,
      minute,
      channelId: ANDROID_CHANNEL_ID,
    },
  });

  await savePrefs({ enabled: true, hour, minute, notificationId });
  return true;
}

/** Cancel the scheduled notification and mark the reminder off. */
export async function cancelDailyReminder(): Promise<void> {
  const prefs = await getReminderPrefs();
  if (prefs.notificationId) {
    await Notifications.cancelScheduledNotificationAsync(prefs.notificationId);
  }
  await savePrefs({ ...prefs, enabled: false, notificationId: null });
}
