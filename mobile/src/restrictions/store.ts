import type { Rule } from './types';

/** Local tally of what the app confirmed as logged on a given day. */
export interface IntakeTally {
  calories: number;
  entries: number;
}

/** Local calendar-day key ('YYYY-MM-DD') for the intake tally. */
export function dayKey(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

/**
 * Persistence port for restriction rules and the daily intake tally that
 * daily_cap rules evaluate against.
 */
export interface RestrictionStore {
  listRules(): Promise<Rule[]>;
  /** Insert or replace by id. */
  saveRule(rule: Rule): Promise<void>;
  deleteRule(id: string): Promise<void>;
  getIntake(day: string): Promise<IntakeTally>;
  /** Add a confirmed log's calories + entry count to the day's tally. */
  addIntake(day: string, calories: number, entries: number): Promise<void>;
}

/** In-memory store for tests and as a safe fallback when SQLite is absent. */
export class MemoryRestrictionStore implements RestrictionStore {
  private rules = new Map<string, Rule>();
  private intake = new Map<string, IntakeTally>();

  async listRules(): Promise<Rule[]> {
    return [...this.rules.values()];
  }

  async saveRule(rule: Rule): Promise<void> {
    this.rules.set(rule.id, rule);
  }

  async deleteRule(id: string): Promise<void> {
    this.rules.delete(id);
  }

  async getIntake(day: string): Promise<IntakeTally> {
    return this.intake.get(day) ?? { calories: 0, entries: 0 };
  }

  async addIntake(day: string, calories: number, entries: number): Promise<void> {
    const current = await this.getIntake(day);
    this.intake.set(day, {
      calories: current.calories + calories,
      entries: current.entries + entries,
    });
  }
}
