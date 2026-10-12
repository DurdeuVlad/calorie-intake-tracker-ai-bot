import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Link } from 'expo-router';

import { useAuth } from '../auth/AuthContext';

export default function HomeScreen() {
  const { email, client, signOut } = useAuth();
  const [providers, setProviders] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const loadStatus = useCallback(async () => {
    setLoading(true);
    setLoadError(false);
    try {
      const status = await client.getLinkStatus();
      setProviders(status.linkedProviders);
    } catch {
      setLoadError(true);
    } finally {
      setLoading(false);
    }
  }, [client]);

  useEffect(() => {
    const id = setTimeout(() => void loadStatus(), 0);
    return () => clearTimeout(id);
  }, [loadStatus]);

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.container}>
        <Text style={styles.title}>Home</Text>
        <Text style={styles.label} testID="account-email">
          {email ?? 'Signed in'}
        </Text>

        <View style={styles.card}>
          <Text style={styles.cardTitle}>Linked providers</Text>
          {loading ? (
            <ActivityIndicator testID="link-status-loading" />
          ) : loadError ? (
            <View style={styles.errorRow}>
              <Text style={styles.errorText} testID="link-status-error">
                Could not load linked providers.
              </Text>
              <Pressable onPress={loadStatus} testID="retry-button">
                <Text style={styles.retry}>Retry</Text>
              </Pressable>
            </View>
          ) : (
            <Text style={styles.providers} testID="linked-providers">
              {providers.length > 0 ? providers.join(', ') : 'None yet'}
            </Text>
          )}
        </View>

        <Link href="/log" asChild>
          <Pressable style={styles.logButton} testID="log-meal-button">
            <Text style={styles.logButtonText}>Log a meal</Text>
          </Pressable>
        </Link>

        <View style={styles.card}>
          <Text style={styles.cardTitle}>Account</Text>
          <Link href="/link" asChild>
            <Pressable style={styles.navRow} testID="linking-button">
              <Text style={styles.navRowText}>Linked accounts</Text>
              <Text style={styles.navRowChevron}>›</Text>
            </Pressable>
          </Link>
          <Link href="/memories" asChild>
            <Pressable style={styles.navRow} testID="memories-button">
              <Text style={styles.navRowText}>Saved memories</Text>
              <Text style={styles.navRowChevron}>›</Text>
            </Pressable>
          </Link>
          <Link href="/restrictions" asChild>
            <Pressable style={styles.navRow} testID="restrictions-button">
              <Text style={styles.navRowText}>Restrictions & reminders</Text>
              <Text style={styles.navRowChevron}>›</Text>
            </Pressable>
          </Link>
        </View>

        <Pressable style={styles.signOut} onPress={() => void signOut()} testID="sign-out-button">
          <Text style={styles.signOutText}>Sign out</Text>
        </Pressable>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#f6f7f9' },
  container: { flex: 1, padding: 24, gap: 16 },
  title: { fontSize: 28, fontWeight: '700' },
  label: { fontSize: 15, color: '#5b5b62' },
  card: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 16,
    gap: 8,
    shadowColor: '#000',
    shadowOpacity: 0.06,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  cardTitle: { fontSize: 13, fontWeight: '600', color: '#8a8a92', textTransform: 'uppercase' },
  providers: { fontSize: 16 },
  errorRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  errorText: { color: '#b3261e', fontSize: 14 },
  retry: { color: '#1a6ef5', fontSize: 14, fontWeight: '600' },
  navRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 10,
  },
  navRowText: { fontSize: 16 },
  navRowChevron: { fontSize: 20, color: '#8a8a92' },
  logButton: {
    backgroundColor: '#1a6ef5',
    borderRadius: 12,
    alignItems: 'center',
    paddingVertical: 14,
  },
  logButtonText: { color: '#fff', fontSize: 16, fontWeight: '600' },
  signOut: { marginTop: 'auto', alignItems: 'center', paddingVertical: 14 },
  signOutText: { color: '#b3261e', fontSize: 16, fontWeight: '600' },
});
