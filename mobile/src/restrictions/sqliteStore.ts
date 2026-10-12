import { openDatabaseSync, type SQLiteDatabase } from 'expo-sqlite';

import type { RestrictionStore, IntakeTally } from './store';
import type { Rule } from './types';

// Storage choice: expo-sqlite, not SecureStore-backed JSON. These are app
// data, not secrets — SecureStore encrypts into the Keychain/Keystore and
// caps values around 2 KB, which would silently bound the user's rule list.
// SQLite has no such cap and matches MISSION_AUDIT §4.7 ("restriction rules
// must live on-device (local SQLite)"), leaving room for sync metadata later.
const DB_NAME = 'restrictions.db';

interface RuleRow {
  id: string;
  kind: Rule['kind'];
  params: string;
  enabled: number;
}

interface IntakeRow {
  calories: number;
  entries: number;
}

export class SqliteRestrictionStore implements RestrictionStore {
  private db: SQLiteDatabase;

  constructor(db: SQLiteDatabase) {
    this.db = db;
    this.db.execSync(`
      CREATE TABLE IF NOT EXISTS rules (
        id TEXT PRIMARY KEY NOT NULL,
        kind TEXT NOT NULL,
        params TEXT NOT NULL,
        enabled INTEGER NOT NULL DEFAULT 1
      );
      CREATE TABLE IF NOT EXISTS intake_tally (
        day TEXT PRIMARY KEY NOT NULL,
        calories REAL NOT NULL DEFAULT 0,
        entries INTEGER NOT NULL DEFAULT 0
      );
    `);
  }

  async listRules(): Promise<Rule[]> {
    const rows = await this.db.getAllAsync<RuleRow>(
      'SELECT id, kind, params, enabled FROM rules ORDER BY rowid',
    );
    return rows.map((row) => ({
      id: row.id,
      kind: row.kind,
      params: JSON.parse(row.params) as Rule['params'],
      enabled: row.enabled === 1,
    }));
  }

  async saveRule(rule: Rule): Promise<void> {
    await this.db.runAsync(
      'INSERT OR REPLACE INTO rules (id, kind, params, enabled) VALUES (?, ?, ?, ?)',
      [rule.id, rule.kind, JSON.stringify(rule.params), rule.enabled ? 1 : 0],
    );
  }

  async deleteRule(id: string): Promise<void> {
    await this.db.runAsync('DELETE FROM rules WHERE id = ?', [id]);
  }

  async getIntake(day: string): Promise<IntakeTally> {
    const row = await this.db.getFirstAsync<IntakeRow>(
      'SELECT calories, entries FROM intake_tally WHERE day = ?',
      [day],
    );
    return row ?? { calories: 0, entries: 0 };
  }

  async addIntake(day: string, calories: number, entries: number): Promise<void> {
    await this.db.runAsync(
      `INSERT INTO intake_tally (day, calories, entries) VALUES (?, ?, ?)
       ON CONFLICT(day) DO UPDATE SET calories = calories + ?, entries = entries + ?`,
      [day, calories, entries, calories, entries],
    );
  }
}

let instance: SqliteRestrictionStore | null = null;

/** Lazily opened shared store. */
export function getRestrictionStore(): RestrictionStore {
  instance ??= new SqliteRestrictionStore(openDatabaseSync(DB_NAME));
  return instance;
}
