import * as Notifications from 'expo-notifications';
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

import {
  cancelDailyReminder,
  getReminderPrefs,
  scheduleDailyReminder,
} from '../src/reminders/schedule';

const mockScheduled = new Map<string, Notifications.NotificationRequestInput>();
let mockSeq = 0;
let mockGranted = true;

jest.mock('expo-notifications', () => ({
  setNotificationHandler: jest.fn(),
  getPermissionsAsync: jest.fn(async () => ({ granted: mockGranted, status: 'granted' })),
  requestPermissionsAsync: jest.fn(async () => ({ granted: mockGranted, status: 'granted' })),
  setNotificationChannelAsync: jest.fn(async () => null),
  scheduleNotificationAsync: jest.fn(async (request: Notifications.NotificationRequestInput) => {
    const id = `notif-${++mockSeq}`;
    mockScheduled.set(id, request);
    return id;
  }),
  cancelScheduledNotificationAsync: jest.fn(async (id: string) => {
    mockScheduled.delete(id);
  }),
  SchedulableTriggerInputTypes: { DAILY: 'daily' },
  AndroidImportance: { DEFAULT: 3 },
}));

// Stateful SecureStore so prefs persist between calls like the real thing.
jest.mock('expo-secure-store', () => {
  const mem = new Map<string, string>();
  return {
    getItemAsync: jest.fn(async (key: string) => mem.get(key) ?? null),
    setItemAsync: jest.fn(async (key: string, value: string) => void mem.set(key, value)),
    deleteItemAsync: jest.fn(async (key: string) => void mem.delete(key)),
  };
});

const mockedSchedule = jest.mocked(Notifications.scheduleNotificationAsync);
const mockedCancel = jest.mocked(Notifications.cancelScheduledNotificationAsync);
const mockedChannel = jest.mocked(Notifications.setNotificationChannelAsync);

beforeEach(async () => {
  mockScheduled.clear();
  mockSeq = 0;
  mockGranted = true;
  jest.clearAllMocks();
  await SecureStore.deleteItemAsync('reminders.daily');
});

describe('scheduleDailyReminder', () => {
  it('schedules a DAILY trigger at the requested local time and persists prefs', async () => {
    const ok = await scheduleDailyReminder(19, 30);

    expect(ok).toBe(true);
    expect(mockedSchedule).toHaveBeenCalledTimes(1);
    const request = mockedSchedule.mock.calls[0][0];
    expect(request.trigger).toMatchObject({ type: 'daily', hour: 19, minute: 30 });
    expect(request.content).toMatchObject({ title: 'Time to log' });

    const prefs = await getReminderPrefs();
    expect(prefs.enabled).toBe(true);
    expect(prefs.hour).toBe(19);
    expect(prefs.minute).toBe(30);
    expect(prefs.notificationId).toBe('notif-1');
  });

  it('sets the Android reminder channel before scheduling', async () => {
    const original = Platform.OS;
    Object.defineProperty(Platform, 'OS', { get: () => 'android' });
    try {
      await scheduleDailyReminder(8, 0);
      expect(mockedChannel).toHaveBeenCalledWith(
        'reminders',
        expect.objectContaining({ name: 'Logging reminders' }),
      );
    } finally {
      Object.defineProperty(Platform, 'OS', { get: () => original });
    }
  });

  it('returns false and schedules nothing when permission is denied', async () => {
    mockGranted = false;
    const ok = await scheduleDailyReminder(19, 0);

    expect(ok).toBe(false);
    expect(mockedSchedule).not.toHaveBeenCalled();
    expect(await getReminderPrefs()).toMatchObject({ enabled: false });
  });

  it('cancels the previous notification when rescheduling', async () => {
    await scheduleDailyReminder(19, 0);
    await scheduleDailyReminder(21, 15);

    expect(mockedCancel).toHaveBeenCalledWith('notif-1');
    expect(mockScheduled.size).toBe(1);
    expect(mockScheduled.has('notif-2')).toBe(true);
    const prefs = await getReminderPrefs();
    expect(prefs.notificationId).toBe('notif-2');
  });
});

describe('cancelDailyReminder', () => {
  it('cancels the mockScheduled notification and marks the reminder off', async () => {
    await scheduleDailyReminder(19, 0);
    await cancelDailyReminder();

    expect(mockedCancel).toHaveBeenCalledWith('notif-1');
    expect(mockScheduled.size).toBe(0);

    const prefs = await getReminderPrefs();
    expect(prefs.enabled).toBe(false);
    expect(prefs.notificationId).toBeNull();
    expect(prefs.hour).toBe(19); // time kept for one-tap re-enable
  });

  it('is a no-op when nothing was mockScheduled', async () => {
    await cancelDailyReminder();
    expect(mockedCancel).not.toHaveBeenCalled();
    expect(await getReminderPrefs()).toMatchObject({ enabled: false });
  });
});
