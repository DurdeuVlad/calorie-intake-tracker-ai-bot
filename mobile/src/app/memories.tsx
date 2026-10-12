import { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';

import { useAuth } from '../auth/AuthContext';
import type { CompanionMemoryItem } from '../api/types';

function formatDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

export default function MemoriesScreen() {
  const { client } = useAuth();
  const [memories, setMemories] = useState<CompanionMemoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(false);
    try {
      const res = await client.listMemories();
      setMemories(res.memories);
    } catch {
      setLoadError(true);
    } finally {
      setLoading(false);
    }
  }, [client]);

  useEffect(() => {
    const id = setTimeout(() => void load(), 0);
    return () => clearTimeout(id);
  }, [load]);

  const remove = useCallback(
    async (memoryId: number) => {
      setDeletingId(memoryId);
      try {
        await client.deleteMemory(memoryId);
        setMemories((prev) => prev.filter((m) => m.id !== memoryId));
      } catch {
        Alert.alert('Could not delete', 'The memory could not be removed — please try again.');
      } finally {
        setDeletingId(null);
      }
    },
    [client],
  );

  const confirmDelete = useCallback(
    (memory: CompanionMemoryItem) => {
      Alert.alert('Delete this memory?', memory.text, [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Delete', style: 'destructive', onPress: () => void remove(memory.id) },
      ]);
    },
    [remove],
  );

  const renderItem = useCallback(
    ({ item }: { item: CompanionMemoryItem }) => (
      <View style={styles.memoryRow} testID={`memory-${item.id}`}>
        <View style={styles.memoryBody}>
          <Text style={styles.memoryText}>{item.text}</Text>
          <Text style={styles.memoryMeta}>
            {[item.kind, item.source, formatDate(item.created_at)].join(' · ')}
          </Text>
        </View>
        <Pressable
          onPress={() => confirmDelete(item)}
          disabled={deletingId === item.id}
          accessibilityRole="button"
          accessibilityLabel={`Delete memory: ${item.text}`}
          testID={`delete-memory-${item.id}`}
          hitSlop={8}
        >
          {deletingId === item.id ? (
            <ActivityIndicator size="small" color="#b3261e" />
          ) : (
            <Text style={styles.deleteText}>Delete</Text>
          )}
        </Pressable>
      </View>
    ),
    [confirmDelete, deletingId],
  );

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.container}>
        <Pressable onPress={() => router.back()} testID="back-button" hitSlop={8}>
          <Text style={styles.back}>‹ Back</Text>
        </Pressable>
        <Text style={styles.title}>Memories</Text>
        <Text style={styles.hint}>
          The agent saves facts it learns about you as you log — review or remove them here.
        </Text>

        {loading ? (
          <ActivityIndicator style={styles.center} testID="memories-loading" />
        ) : loadError ? (
          <View style={styles.center}>
            <Text style={styles.errorText} testID="memories-error">
              Could not load your memories.
            </Text>
            <Pressable onPress={() => void load()} testID="retry-button">
              <Text style={styles.retry}>Retry</Text>
            </Pressable>
          </View>
        ) : (
          <FlatList
            data={memories}
            keyExtractor={(item) => String(item.id)}
            renderItem={renderItem}
            contentContainerStyle={memories.length === 0 && styles.emptyContainer}
            ListEmptyComponent={
              <Text style={styles.empty} testID="memories-empty">
                Nothing saved yet — the agent saves facts it learns about you. They will show up
                here so you can review or remove them.
              </Text>
            }
          />
        )}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#f6f7f9' },
  container: { flex: 1, padding: 24, gap: 12 },
  back: { fontSize: 16, color: '#1a6ef5', fontWeight: '600' },
  title: { fontSize: 28, fontWeight: '700' },
  hint: { fontSize: 15, color: '#5b5b62' },
  center: { marginTop: 48, alignItems: 'center', gap: 12 },
  errorText: { color: '#b3261e', fontSize: 14 },
  retry: { color: '#1a6ef5', fontSize: 14, fontWeight: '600' },
  emptyContainer: { flexGrow: 1, justifyContent: 'center' },
  empty: { fontSize: 15, color: '#5b5b62', textAlign: 'center', lineHeight: 22 },
  memoryRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 16,
    marginTop: 12,
    shadowColor: '#000',
    shadowOpacity: 0.06,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  memoryBody: { flex: 1, gap: 4 },
  memoryText: { fontSize: 16, lineHeight: 22 },
  memoryMeta: {
    fontSize: 13,
    color: '#8a8a92',
    textTransform: 'capitalize',
  },
  deleteText: { color: '#b3261e', fontSize: 14, fontWeight: '600' },
});
