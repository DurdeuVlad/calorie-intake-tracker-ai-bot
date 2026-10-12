import { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';

import { useAuth } from '../auth/AuthContext';
import { ApiError, userFacingMessage } from '../api/errors';
import type { LinkIssueResponse } from '../api/types';

function formatExpiry(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function LinkScreen() {
  const { client } = useAuth();
  const [providers, setProviders] = useState<string[] | null>(null);
  const [statusError, setStatusError] = useState(false);

  const [issuing, setIssuing] = useState(false);
  const [issued, setIssued] = useState<LinkIssueResponse | null>(null);
  const [issueError, setIssueError] = useState<string | null>(null);

  const [code, setCode] = useState('');
  const [redeeming, setRedeeming] = useState(false);
  const [redeemResult, setRedeemResult] = useState<{ ok: boolean; text: string } | null>(null);

  const loadStatus = useCallback(async () => {
    setStatusError(false);
    try {
      const status = await client.getLinkStatus();
      setProviders(status.linkedProviders);
    } catch {
      setStatusError(true);
    }
  }, [client]);

  useEffect(() => {
    const id = setTimeout(() => void loadStatus(), 0);
    return () => clearTimeout(id);
  }, [loadStatus]);

  const showCode = useCallback(async () => {
    if (issuing) return;
    setIssuing(true);
    setIssueError(null);
    try {
      setIssued(await client.issueLinkCode());
    } catch (err) {
      setIssueError(userFacingMessage(err));
    } finally {
      setIssuing(false);
    }
  }, [client, issuing]);

  const redeem = useCallback(async () => {
    const trimmed = code.trim();
    if (!trimmed || redeeming) return;
    setRedeeming(true);
    setRedeemResult(null);
    try {
      const status = await client.redeemLinkCode(trimmed);
      setProviders(status.linkedProviders);
      setCode('');
      setRedeemResult({ ok: true, text: 'Linked — this journal is now shared with Telegram.' });
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setRedeemResult({
          ok: false,
          text: 'This account already has journal data and cannot be linked to another one.',
        });
      } else if (err instanceof ApiError && err.status === 400) {
        setRedeemResult({
          ok: false,
          text: 'That code is invalid or expired — check it in Telegram and try again.',
        });
      } else {
        setRedeemResult({ ok: false, text: userFacingMessage(err) });
      }
    } finally {
      setRedeeming(false);
    }
  }, [client, code, redeeming]);

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
        <Pressable onPress={() => router.back()} testID="back-button" hitSlop={8}>
          <Text style={styles.back}>‹ Back</Text>
        </Pressable>
        <Text style={styles.title}>Linked accounts</Text>
        <Text style={styles.hint}>
          Link Telegram to this account so both share the same food journal.
        </Text>

        <View style={styles.card}>
          <Text style={styles.cardTitle}>Linked providers</Text>
          {providers === null && !statusError ? (
            <ActivityIndicator testID="link-status-loading" />
          ) : statusError ? (
            <View style={styles.errorRow}>
              <Text style={styles.errorText} testID="link-status-error">
                Could not load linked providers.
              </Text>
              <Pressable onPress={() => void loadStatus()} testID="retry-button">
                <Text style={styles.retry}>Retry</Text>
              </Pressable>
            </View>
          ) : (
            <Text style={styles.providers} testID="linked-providers">
              {providers && providers.length > 0 ? providers.join(', ') : 'None yet'}
            </Text>
          )}
        </View>

        <View style={styles.card}>
          <Text style={styles.cardTitle}>Link this app to Telegram</Text>
          <Text style={styles.cardHint}>
            Show a code, then send it to the bot on the Telegram account you want to share this
            journal with.
          </Text>
          <Pressable
            style={[styles.button, issuing && styles.buttonDisabled]}
            onPress={() => void showCode()}
            disabled={issuing}
            accessibilityRole="button"
            testID="show-code-button"
          >
            {issuing ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.buttonText}>Show link code</Text>
            )}
          </Pressable>
          {issueError && (
            <Text style={styles.errorText} testID="issue-error">
              {issueError}
            </Text>
          )}
          {issued && (
            <View style={styles.codeBlock} testID="issued-code-block">
              <Text style={styles.codeValue} testID="issued-code">
                {issued.code}
              </Text>
              <Text style={styles.codeExpiry} testID="issued-code-expiry">
                Expires {formatExpiry(issued.expiresAt)}
              </Text>
              <Text style={styles.codeInstructions}>
                In Telegram, open the bot and send: link {issued.code}
              </Text>
            </View>
          )}
        </View>

        <View style={styles.card}>
          <Text style={styles.cardTitle}>Redeem a Telegram code</Text>
          <Text style={styles.cardHint}>
            If the bot showed you a link code, enter it here to pull that journal into this
            account.
          </Text>
          <View style={styles.redeemRow}>
            <TextInput
              style={styles.input}
              value={code}
              onChangeText={setCode}
              placeholder="e.g. ABCD1234"
              autoCapitalize="characters"
              autoCorrect={false}
              maxLength={32}
              editable={!redeeming}
              testID="redeem-input"
            />
            <Pressable
              style={[styles.button, (!code.trim() || redeeming) && styles.buttonDisabled]}
              onPress={() => void redeem()}
              disabled={!code.trim() || redeeming}
              accessibilityRole="button"
              testID="redeem-button"
            >
              {redeeming ? (
                <ActivityIndicator color="#fff" />
              ) : (
                <Text style={styles.buttonText}>Redeem</Text>
              )}
            </Pressable>
          </View>
          {redeemResult && (
            <Text
              style={redeemResult.ok ? styles.successText : styles.errorText}
              testID="redeem-result"
            >
              {redeemResult.text}
            </Text>
          )}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#f6f7f9' },
  container: { padding: 24, gap: 16 },
  back: { fontSize: 16, color: '#1a6ef5', fontWeight: '600' },
  title: { fontSize: 28, fontWeight: '700' },
  hint: { fontSize: 15, color: '#5b5b62' },
  card: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 16,
    gap: 10,
    shadowColor: '#000',
    shadowOpacity: 0.06,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  cardTitle: { fontSize: 13, fontWeight: '600', color: '#8a8a92', textTransform: 'uppercase' },
  cardHint: { fontSize: 14, color: '#5b5b62', lineHeight: 20 },
  providers: { fontSize: 16 },
  errorRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  errorText: { color: '#b3261e', fontSize: 14 },
  successText: { color: '#1e7d34', fontSize: 14, fontWeight: '600' },
  retry: { color: '#1a6ef5', fontSize: 14, fontWeight: '600' },
  button: {
    backgroundColor: '#1a6ef5',
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 12,
    paddingHorizontal: 18,
    minHeight: 44,
  },
  buttonDisabled: { opacity: 0.4 },
  buttonText: { color: '#fff', fontSize: 16, fontWeight: '600' },
  codeBlock: { alignItems: 'center', gap: 6, paddingVertical: 8 },
  codeValue: {
    fontSize: 32,
    fontWeight: '700',
    letterSpacing: 4,
    fontVariant: ['tabular-nums'],
  },
  codeExpiry: { fontSize: 13, color: '#8a8a92' },
  codeInstructions: { fontSize: 14, color: '#5b5b62', textAlign: 'center' },
  redeemRow: { flexDirection: 'row', gap: 8 },
  input: {
    flex: 1,
    backgroundColor: '#f6f7f9',
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 16,
    minHeight: 44,
  },
});
