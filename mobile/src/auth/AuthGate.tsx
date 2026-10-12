import { useRouter, useSegments } from 'expo-router';
import { useEffect, type ReactNode } from 'react';
import { ActivityIndicator, StyleSheet, View } from 'react-native';

import { useAuth, type AuthStatus } from './AuthContext';

const AUTH_GROUP = '(auth)';
const LOGIN_ROUTE = '/(auth)/login';
const HOME_ROUTE = '/';

/** Pure routing decision, separated so the gate can be tested without a navigator. */
export function redirectFor(status: AuthStatus, inAuthGroup: boolean): string | null {
  if (status === 'loading') return null;
  if (status === 'unauthenticated' && !inAuthGroup) return LOGIN_ROUTE;
  if (status === 'authenticated' && inAuthGroup) return HOME_ROUTE;
  return null;
}

export function AuthGate({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const segments = useSegments();
  const router = useRouter();

  useEffect(() => {
    const target = redirectFor(status, segments[0] === AUTH_GROUP);
    if (target) router.replace(target);
  }, [status, segments, router]);

  if (status === 'loading') {
    return (
      <View style={styles.loading} testID="auth-loading">
        <ActivityIndicator size="large" />
      </View>
    );
  }

  return <>{children}</>;
}

const styles = StyleSheet.create({
  loading: { flex: 1, alignItems: 'center', justifyContent: 'center' },
});
