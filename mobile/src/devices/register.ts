import { Platform } from 'react-native';
import Constants from 'expo-constants';
import * as Notifications from 'expo-notifications';
import { getLocales } from 'expo-localization';

import type { ApiClient } from '../api/client';

/**
 * Fire-and-forget POST /api/v1/devices. Called when the session becomes
 * authenticated (fresh login, signup, or a restored session at app start).
 * Every failure — denied permission, missing EAS projectId, Expo Go's lack of
 * push support, an unreachable server — is swallowed: registration is
 * best-effort background work and must never block or alert the UI.
 */
export async function registerCurrentDevice(client: ApiClient): Promise<void> {
  try {
    if (Platform.OS !== 'ios' && Platform.OS !== 'android') return;

    const existing = await Notifications.getPermissionsAsync();
    const granted =
      existing.granted || (await Notifications.requestPermissionsAsync()).granted;
    if (!granted) return;

    // projectId defaults to Constants.expoConfig.extra.eas.projectId; without an
    // EAS project this throws, which is fine — nothing registers until one exists.
    const { data: pushToken } = await Notifications.getExpoPushTokenAsync();

    await client.registerDevice({
      platform: Platform.OS,
      push_token: pushToken,
      app_version: Constants.expoConfig?.version ?? Constants.nativeAppVersion ?? null,
      locale: getLocales()[0]?.languageTag ?? null,
    });
  } catch {
    // Best-effort only — see the docblock.
  }
}
