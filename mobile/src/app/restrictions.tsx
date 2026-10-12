import { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import * as Crypto from 'expo-crypto';

import { describeRule } from '../restrictions/engine';
import { getRestrictionStore } from '../restrictions/sqliteStore';
import type { RestrictionStore } from '../restrictions/store';
import type { Rule, RuleKind } from '../restrictions/types';
import {
  cancelDailyReminder,
  getReminderPrefs,
  scheduleDailyReminder,
} from '../reminders/schedule';

const TIME_RE = /^([01]?\d|2[0-3]):[0-5]\d$/;

function parseTime(value: string): { hour: number; minute: number } | null {
  if (!TIME_RE.test(value.trim())) return null;
  const [hour, minute] = value.trim().split(':').map(Number);
  return { hour, minute };
}

export default function RestrictionsScreen() {
  const [store] = useState<RestrictionStore>(() => getRestrictionStore());
  const [rules, setRules] = useState<Rule[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const [kind, setKind] = useState<RuleKind>('time_window');
  const [startTime, setStartTime] = useState('21:00');
  const [endTime, setEndTime] = useState('07:00');
  const [maxCalories, setMaxCalories] = useState('');
  const [maxEntries, setMaxEntries] = useState('');
  const [keyword, setKeyword] = useState('');
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const [reminderTime, setReminderTime] = useState('19:00');
  const [reminderEnabled, setReminderEnabled] = useState(false);
  const [reminderError, setReminderError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(false);
    try {
      const [list, prefs] = await Promise.all([store.listRules(), getReminderPrefs()]);
      setRules(list);
      setReminderEnabled(prefs.enabled);
      setReminderTime(
        `${String(prefs.hour).padStart(2, '0')}:${String(prefs.minute).padStart(2, '0')}`,
      );
    } catch {
      setLoadError(true);
    } finally {
      setLoading(false);
    }
  }, [store]);

  useEffect(() => {
    const id = setTimeout(() => void load(), 0);
    return () => clearTimeout(id);
  }, [load]);

  const buildRule = useCallback((): Rule | null => {
    setFormError(null);
    if (kind === 'time_window') {
      if (!parseTime(startTime) || !parseTime(endTime)) {
        setFormError('Times must be HH:MM, e.g. 21:00.');
        return null;
      }
      return {
        id: Crypto.randomUUID(),
        kind,
        params: { start: startTime.trim(), end: endTime.trim() },
        enabled: true,
      };
    }
    if (kind === 'daily_cap') {
      const calories = maxCalories.trim() ? Number(maxCalories) : 0;
      const entries = maxEntries.trim() ? Number(maxEntries) : 0;
      if (
        (calories <= 0 && entries <= 0) ||
        !Number.isInteger(calories) ||
        !Number.isInteger(entries) ||
        calories < 0 ||
        entries < 0
      ) {
        setFormError('Set at least one positive whole-number cap.');
        return null;
      }
      return {
        id: Crypto.randomUUID(),
        kind,
        params: {
          ...(calories > 0 ? { maxCalories: calories } : {}),
          ...(entries > 0 ? { maxEntries: entries } : {}),
        },
        enabled: true,
      };
    }
    if (!keyword.trim()) {
      setFormError('Enter a word to watch for.');
      return null;
    }
    return {
      id: Crypto.randomUUID(),
      kind,
      params: { keyword: keyword.trim() },
      enabled: true,
    };
  }, [kind, startTime, endTime, maxCalories, maxEntries, keyword]);

  const addRule = useCallback(async () => {
    const rule = buildRule();
    if (!rule || saving) return;
    setSaving(true);
    try {
      await store.saveRule(rule);
      setRules((prev) => [...prev, rule]);
      setKeyword('');
      setMaxCalories('');
      setMaxEntries('');
    } catch {
      setFormError('Could not save the rule — please try again.');
    } finally {
      setSaving(false);
    }
  }, [buildRule, saving, store]);

  const toggleRule = useCallback(
    async (rule: Rule, enabled: boolean) => {
      const updated = { ...rule, enabled };
      setRules((prev) => prev.map((r) => (r.id === rule.id ? updated : r)));
      try {
        await store.saveRule(updated);
      } catch {
        setRules((prev) => prev.map((r) => (r.id === rule.id ? rule : r)));
      }
    },
    [store],
  );

  const removeRule = useCallback(
    async (rule: Rule) => {
      try {
        await store.deleteRule(rule.id);
        setRules((prev) => prev.filter((r) => r.id !== rule.id));
      } catch {
        Alert.alert('Could not delete', 'The rule could not be removed — please try again.');
      }
    },
    [store],
  );

  const confirmDelete = useCallback(
    (rule: Rule) => {
      Alert.alert('Delete this rule?', describeRule(rule), [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Delete', style: 'destructive', onPress: () => void removeRule(rule) },
      ]);
    },
    [removeRule],
  );

  const toggleReminder = useCallback(
    async (enabled: boolean) => {
      setReminderError(null);
      if (!enabled) {
        setReminderEnabled(false);
        await cancelDailyReminder();
        return;
      }
      const time = parseTime(reminderTime);
      if (!time) {
        setReminderError('Reminder time must be HH:MM, e.g. 19:00.');
        return;
      }
      const scheduled = await scheduleDailyReminder(time.hour, time.minute);
      if (scheduled) {
        setReminderEnabled(true);
      } else {
        setReminderError('Notifications are off — enable them in Settings to use reminders.');
      }
    },
    [reminderTime],
  );

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
        <Pressable onPress={() => router.back()} testID="back-button" hitSlop={8}>
          <Text style={styles.back}>‹ Back</Text>
        </Pressable>
        <Text style={styles.title}>Restrictions</Text>
        <Text style={styles.hint}>
          Local nudges only — rules check your log before it sends and warn you, but never block.
          Nothing here leaves the device.
        </Text>

        <View style={styles.card}>
          <Text style={styles.cardTitle}>Daily reminder</Text>
          <View style={styles.reminderRow}>
            <TextInput
              style={styles.timeInput}
              value={reminderTime}
              onChangeText={setReminderTime}
              placeholder="19:00"
              keyboardType="numbers-and-punctuation"
              testID="reminder-time-input"
            />
            <Switch
              value={reminderEnabled}
              onValueChange={(v) => void toggleReminder(v)}
              testID="reminder-switch"
            />
          </View>
          {reminderError && (
            <Text style={styles.formError} testID="reminder-error">
              {reminderError}
            </Text>
          )}
          <Text style={styles.reminderHint}>
            A local notification nudges you to log each day at this time.
          </Text>
        </View>

        {loading ? (
          <ActivityIndicator style={styles.center} testID="rules-loading" />
        ) : loadError ? (
          <View style={styles.center}>
            <Text style={styles.errorText} testID="rules-error">
              Could not load your rules.
            </Text>
            <Pressable onPress={() => void load()} testID="retry-button">
              <Text style={styles.retry}>Retry</Text>
            </Pressable>
          </View>
        ) : (
          <>
            {rules.length === 0 ? (
              <Text style={styles.empty} testID="rules-empty">
                No rules yet — add one below and it will nudge you when you log.
              </Text>
            ) : (
              rules.map((rule) => (
                <View key={rule.id} style={styles.ruleRow} testID={`rule-${rule.id}`}>
                  <View style={styles.ruleBody}>
                    <Text style={styles.ruleText}>{describeRule(rule)}</Text>
                  </View>
                  <Switch
                    value={rule.enabled}
                    onValueChange={(v) => void toggleRule(rule, v)}
                    testID={`toggle-rule-${rule.id}`}
                  />
                  <Pressable
                    onPress={() => confirmDelete(rule)}
                    accessibilityRole="button"
                    accessibilityLabel={`Delete rule: ${describeRule(rule)}`}
                    testID={`delete-rule-${rule.id}`}
                    hitSlop={8}
                  >
                    <Text style={styles.deleteText}>Delete</Text>
                  </Pressable>
                </View>
              ))
            )}

            <View style={styles.card}>
              <Text style={styles.cardTitle}>Add a rule</Text>
              <View style={styles.kindRow}>
                {(
                  [
                    ['time_window', 'Time window'],
                    ['daily_cap', 'Daily cap'],
                    ['keyword', 'Keyword'],
                  ] as [RuleKind, string][]
                ).map(([value, label]) => (
                  <Pressable
                    key={value}
                    style={[styles.kindPill, kind === value && styles.kindPillActive]}
                    onPress={() => setKind(value)}
                    testID={`kind-${value}`}
                  >
                    <Text style={[styles.kindText, kind === value && styles.kindTextActive]}>
                      {label}
                    </Text>
                  </Pressable>
                ))}
              </View>

              {kind === 'time_window' && (
                <View style={styles.fieldRow}>
                  <TextInput
                    style={styles.timeInput}
                    value={startTime}
                    onChangeText={setStartTime}
                    placeholder="21:00"
                    keyboardType="numbers-and-punctuation"
                    testID="start-time-input"
                  />
                  <Text style={styles.fieldSep}>to</Text>
                  <TextInput
                    style={styles.timeInput}
                    value={endTime}
                    onChangeText={setEndTime}
                    placeholder="07:00"
                    keyboardType="numbers-and-punctuation"
                    testID="end-time-input"
                  />
                </View>
              )}
              {kind === 'daily_cap' && (
                <View style={styles.fieldRow}>
                  <TextInput
                    style={styles.numInput}
                    value={maxCalories}
                    onChangeText={setMaxCalories}
                    placeholder="Max kcal"
                    keyboardType="number-pad"
                    testID="max-calories-input"
                  />
                  <TextInput
                    style={styles.numInput}
                    value={maxEntries}
                    onChangeText={setMaxEntries}
                    placeholder="Max entries"
                    keyboardType="number-pad"
                    testID="max-entries-input"
                  />
                </View>
              )}
              {kind === 'keyword' && (
                <TextInput
                  style={styles.textInput}
                  value={keyword}
                  onChangeText={setKeyword}
                  placeholder="e.g. chocolate"
                  testID="keyword-input"
                />
              )}

              {formError && (
                <Text style={styles.formError} testID="form-error">
                  {formError}
                </Text>
              )}
              <Pressable
                style={[styles.addButton, saving && styles.addButtonDisabled]}
                onPress={() => void addRule()}
                disabled={saving}
                accessibilityRole="button"
                testID="add-rule-button"
              >
                <Text style={styles.addButtonText}>Add rule</Text>
              </Pressable>
            </View>
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#f6f7f9' },
  container: { padding: 24, gap: 12 },
  back: { fontSize: 16, color: '#1a6ef5', fontWeight: '600' },
  title: { fontSize: 28, fontWeight: '700' },
  hint: { fontSize: 15, color: '#5b5b62' },
  center: { marginTop: 32, alignItems: 'center', gap: 12 },
  errorText: { color: '#b3261e', fontSize: 14 },
  retry: { color: '#1a6ef5', fontSize: 14, fontWeight: '600' },
  empty: { fontSize: 15, color: '#5b5b62', textAlign: 'center', marginVertical: 12 },
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
  reminderRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  reminderHint: { fontSize: 13, color: '#8a8a92' },
  ruleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 16,
    shadowColor: '#000',
    shadowOpacity: 0.06,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  ruleBody: { flex: 1 },
  ruleText: { fontSize: 15 },
  deleteText: { color: '#b3261e', fontSize: 14, fontWeight: '600' },
  kindRow: { flexDirection: 'row', gap: 8 },
  kindPill: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 999,
    backgroundColor: '#eef0f4',
  },
  kindPillActive: { backgroundColor: '#1a6ef5' },
  kindText: { fontSize: 14, color: '#3c3c43', fontWeight: '500' },
  kindTextActive: { color: '#fff' },
  fieldRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  fieldSep: { fontSize: 14, color: '#5b5b62' },
  timeInput: {
    width: 84,
    backgroundColor: '#f6f7f9',
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 16,
    textAlign: 'center',
  },
  numInput: {
    flex: 1,
    backgroundColor: '#f6f7f9',
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 16,
  },
  textInput: {
    backgroundColor: '#f6f7f9',
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 16,
  },
  formError: { color: '#b3261e', fontSize: 13 },
  addButton: {
    backgroundColor: '#1a6ef5',
    borderRadius: 12,
    alignItems: 'center',
    paddingVertical: 12,
  },
  addButtonDisabled: { opacity: 0.4 },
  addButtonText: { color: '#fff', fontSize: 15, fontWeight: '600' },
});
