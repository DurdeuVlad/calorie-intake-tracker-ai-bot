import { useCallback, useRef, useState } from 'react';
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
import {
  RecordingPresets,
  requestRecordingPermissionsAsync,
  setAudioModeAsync,
  useAudioRecorder,
  useAudioRecorderState,
} from 'expo-audio';

import { useAuth } from '../auth/AuthContext';
import { userFacingMessage } from '../api/errors';
import type { JournalActionResult, MessageResponse } from '../api/types';

// RecordingPresets.HIGH_QUALITY is .m4a/AAC on both iOS and Android, which the
// backend transcriber accepts.
const RECORDING_MIME_TYPE = 'audio/m4a';

export default function LogScreen() {
  const { client } = useAuth();
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const recorderState = useAudioRecorderState(recorder);

  const [text, setText] = useState('');
  const [recording, setRecording] = useState(false);
  const [sending, setSending] = useState(false);
  const [micDenied, setMicDenied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<MessageResponse | null>(null);
  // Tracks the physical press across the async permission/prepare steps, so a
  // release that lands mid-setup can still cancel the recording before it starts.
  const pressHeld = useRef(false);

  const startRecording = useCallback(async () => {
    if (recording || sending || pressHeld.current) return;
    pressHeld.current = true;
    setError(null);

    const permission = await requestRecordingPermissionsAsync();
    if (!permission.granted) {
      pressHeld.current = false;
      setMicDenied(true);
      return;
    }
    setMicDenied(false);
    setResult(null);

    try {
      await setAudioModeAsync({ allowsRecording: true, playsInSilentMode: true });
      await recorder.prepareToRecordAsync();
      if (!pressHeld.current) {
        void setAudioModeAsync({ allowsRecording: false, playsInSilentMode: true });
        return;
      }
      recorder.record();
      setRecording(true);
    } catch (err) {
      pressHeld.current = false;
      void setAudioModeAsync({ allowsRecording: false, playsInSilentMode: true });
      setError(userFacingMessage(err));
    }
  }, [recorder, recording, sending]);

  const stopAndSend = useCallback(async () => {
    pressHeld.current = false;
    if (!recording) return;
    setRecording(false);
    setSending(true);

    try {
      await recorder.stop();
    } catch (err) {
      setError(userFacingMessage(err));
    }
    void setAudioModeAsync({ allowsRecording: false, playsInSilentMode: true });

    const uri = recorder.uri;
    if (!uri) {
      setError('Nothing was recorded — hold the mic button and try again.');
      setSending(false);
      return;
    }

    try {
      setResult(await client.sendAudioMessage({ uri, mimeType: RECORDING_MIME_TYPE }));
    } catch (err) {
      setError(userFacingMessage(err));
    } finally {
      setSending(false);
    }
  }, [client, recorder, recording]);

  const sendText = useCallback(async () => {
    const trimmed = text.trim();
    if (!trimmed || sending || recording) return;
    setSending(true);
    setError(null);

    try {
      setResult(await client.sendMessage({ text: trimmed }));
      setText('');
    } catch (err) {
      setError(userFacingMessage(err));
    } finally {
      setSending(false);
    }
  }, [client, text, sending, recording]);

  const busy = recording || sending;

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
        <Text style={styles.title}>Log a meal</Text>
        <Text style={styles.hint}>
          Hold the mic and say what you ate — Romanian, English, or both — or type it below.
        </Text>

        <View style={styles.micArea}>
          <Pressable
            style={[styles.micButton, recording && styles.micButtonActive]}
            onPressIn={() => void startRecording()}
            onPressOut={() => void stopAndSend()}
            disabled={sending}
            accessibilityRole="button"
            accessibilityLabel={recording ? 'Release to send voice note' : 'Hold to record'}
            testID="mic-button"
          >
            {sending ? (
              <ActivityIndicator color="#fff" testID="sending-spinner" />
            ) : (
              <Text style={styles.micIcon}>{recording ? '■' : '●'}</Text>
            )}
          </Pressable>
          <Text style={styles.micLabel} testID="mic-label">
            {recording
              ? `Recording… ${Math.round(recorderState.durationMillis / 1000)}s — release to send`
              : sending
                ? 'Sending…'
                : 'Hold to talk'}
          </Text>
          {micDenied && (
            <Text style={styles.denied} testID="mic-denied">
              Microphone access is off — enable it in Settings to log by voice, or type below.
            </Text>
          )}
        </View>

        <View style={styles.textRow}>
          <TextInput
            style={styles.input}
            value={text}
            onChangeText={setText}
            placeholder="e.g. two eggs and a slice of toast"
            multiline
            editable={!busy}
            testID="text-input"
          />
          <Pressable
            style={[styles.sendButton, (!text.trim() || busy) && styles.sendButtonDisabled]}
            onPress={() => void sendText()}
            disabled={!text.trim() || busy}
            accessibilityRole="button"
            testID="send-text-button"
          >
            <Text style={styles.sendButtonText}>Send</Text>
          </Pressable>
        </View>

        {error && (
          <Text style={styles.error} testID="send-error">
            {error}
          </Text>
        )}

        {result && (
          <View style={styles.response}>
            <Text style={styles.reply} testID="agent-reply">
              {result.reply}
            </Text>
            <ConfirmationCard actions={result.actions} />
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

/** Read-only v1 card: what the agent's apply_journal_actions actually logged. */
function ConfirmationCard({ actions }: { actions: JournalActionResult[] }) {
  if (actions.length === 0) return null;
  return (
    <View style={styles.card} testID="confirmation-card">
      <Text style={styles.cardTitle}>What was logged</Text>
      {actions.map((action, index) => (
        <View key={index} style={styles.actionRow} testID={`action-${index}`}>
          {action.ok ? (
            <>
              <Text style={styles.actionDescription}>
                {action.entry?.description ?? action.type}
              </Text>
              <Text style={styles.actionMeta}>
                {[
                  action.entry?.calories != null ? `${action.entry.calories} kcal` : null,
                  action.date ?? action.entry?.eaten_at ?? null,
                ]
                  .filter(Boolean)
                  .join(' · ')}
              </Text>
            </>
          ) : (
            <Text style={styles.actionFailed}>
              {action.message ?? 'Could not apply this change.'}
            </Text>
          )}
        </View>
      ))}
      <Text style={styles.confirmedBadge} testID="confirmed-badge">
        ✓ Confirmed by the app
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#f6f7f9' },
  container: { padding: 24, gap: 16 },
  title: { fontSize: 28, fontWeight: '700' },
  hint: { fontSize: 15, color: '#5b5b62' },
  micArea: { alignItems: 'center', gap: 12, paddingVertical: 8 },
  micButton: {
    width: 88,
    height: 88,
    borderRadius: 44,
    backgroundColor: '#1a6ef5',
    alignItems: 'center',
    justifyContent: 'center',
  },
  micButtonActive: { backgroundColor: '#b3261e' },
  micIcon: { fontSize: 32, color: '#fff' },
  micLabel: { fontSize: 14, color: '#5b5b62' },
  denied: { fontSize: 13, color: '#b3261e', textAlign: 'center' },
  textRow: { flexDirection: 'row', gap: 8, alignItems: 'flex-end' },
  input: {
    flex: 1,
    backgroundColor: '#fff',
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 16,
    minHeight: 48,
    maxHeight: 120,
  },
  sendButton: {
    backgroundColor: '#1a6ef5',
    borderRadius: 12,
    paddingHorizontal: 18,
    paddingVertical: 14,
  },
  sendButtonDisabled: { opacity: 0.4 },
  sendButtonText: { color: '#fff', fontSize: 16, fontWeight: '600' },
  error: { color: '#b3261e', fontSize: 14 },
  response: { gap: 12 },
  reply: { fontSize: 16, lineHeight: 22 },
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
  actionRow: { gap: 2 },
  actionDescription: { fontSize: 16 },
  actionMeta: { fontSize: 13, color: '#5b5b62' },
  actionFailed: { fontSize: 14, color: '#b3261e' },
  confirmedBadge: { fontSize: 13, fontWeight: '600', color: '#1e7d34', marginTop: 4 },
});
