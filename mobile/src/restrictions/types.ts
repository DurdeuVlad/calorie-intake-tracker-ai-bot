/**
 * On-device restriction rules — local nudges evaluated before a meal log is
 * sent. Rules are advisory only: evaluate() produces nudge decisions, never
 * blocks. See docs/MISSION_AUDIT.md §4.7 — restrictions live on-device.
 */

export type RuleKind = 'time_window' | 'daily_cap' | 'keyword';

/** 'HH:MM' 24h local time, e.g. '21:30'. */
export type LocalTime = string;

export interface TimeWindowParams {
  /** Nudge while the local time is inside [start, end); may wrap midnight. */
  start: LocalTime;
  end: LocalTime;
}

export interface DailyCapParams {
  /** Nudge when today's logged calories reach this. 0/omitted = no cap. */
  maxCalories?: number;
  /** Nudge when today's logged entry count reaches this. 0/omitted = no cap. */
  maxEntries?: number;
}

export interface KeywordParams {
  /** Nudge when the submitted text contains this (case-insensitive). */
  keyword: string;
}

export type RuleParams = TimeWindowParams | DailyCapParams | KeywordParams;

export interface Rule {
  id: string;
  kind: RuleKind;
  params: RuleParams;
  enabled: boolean;
}

/** What evaluate() needs from the caller. All local — no server round-trip. */
export interface EvaluationContext {
  now: Date;
  /** Text about to be submitted; '' for voice notes. */
  text: string;
  /** Local tally of what was already logged today. */
  caloriesToday: number;
  entriesToday: number;
}

/** One triggered rule. `message` is user-facing, shown in the nudge banner. */
export interface Nudge {
  ruleId: string;
  kind: RuleKind;
  message: string;
}
