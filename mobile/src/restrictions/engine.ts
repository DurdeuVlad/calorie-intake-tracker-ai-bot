import type {
  DailyCapParams,
  EvaluationContext,
  KeywordParams,
  Nudge,
  Rule,
  TimeWindowParams,
} from './types';

/** Minutes since local midnight. Returns null for malformed 'HH:MM'. */
function toMinutes(value: string): number | null {
  const match = /^(\d{1,2}):(\d{2})$/.exec(value.trim());
  if (!match) return null;
  const hour = Number(match[1]);
  const minute = Number(match[2]);
  if (hour > 23 || minute > 59) return null;
  return hour * 60 + minute;
}

/** True when `now` is inside [start, end). Windows may wrap midnight. */
function insideWindow(nowMinutes: number, start: number, end: number): boolean {
  if (start === end) return false; // empty window — never nags
  if (start < end) return nowMinutes >= start && nowMinutes < end;
  return nowMinutes >= start || nowMinutes < end; // overnight, e.g. 21:00–07:00
}

function evaluateRule(rule: Rule, ctx: EvaluationContext): Nudge | null {
  switch (rule.kind) {
    case 'time_window': {
      const { start, end } = rule.params as TimeWindowParams;
      const startM = toMinutes(start);
      const endM = toMinutes(end);
      if (startM == null || endM == null) return null;
      const nowM = ctx.now.getHours() * 60 + ctx.now.getMinutes();
      if (!insideWindow(nowM, startM, endM)) return null;
      return {
        ruleId: rule.id,
        kind: rule.kind,
        message: `You set a no-logging window for ${start}–${end}. Still okay to log — just a heads-up.`,
      };
    }
    case 'daily_cap': {
      const { maxCalories = 0, maxEntries = 0 } = rule.params as DailyCapParams;
      const hitCalories = maxCalories > 0 && ctx.caloriesToday >= maxCalories;
      const hitEntries = maxEntries > 0 && ctx.entriesToday >= maxEntries;
      if (!hitCalories && !hitEntries) return null;
      const parts: string[] = [];
      if (hitCalories) parts.push(`${ctx.caloriesToday} of ${maxCalories} kcal`);
      if (hitEntries) parts.push(`${ctx.entriesToday} of ${maxEntries} entries`);
      return {
        ruleId: rule.id,
        kind: rule.kind,
        message: `Daily cap reached — you've already logged ${parts.join(' and ')} today.`,
      };
    }
    case 'keyword': {
      const { keyword } = rule.params as KeywordParams;
      const needle = keyword.trim().toLowerCase();
      if (!needle) return null;
      if (!ctx.text.toLowerCase().includes(needle)) return null;
      return {
        ruleId: rule.id,
        kind: rule.kind,
        message: `Heads-up — "${keyword.trim()}" is on your watch list.`,
      };
    }
  }
}

/**
 * Pure evaluation of enabled rules against the current context. Returns one
 * Nudge per triggered rule, in rule order. Advisory only — the caller decides
 * what to show; nothing here prevents the send.
 */
export function evaluate(rules: Rule[], ctx: EvaluationContext): Nudge[] {
  return rules
    .filter((rule) => rule.enabled)
    .map((rule) => evaluateRule(rule, ctx))
    .filter((nudge): nudge is Nudge => nudge !== null);
}

/** One-line description for the rules list UI. */
export function describeRule(rule: Rule): string {
  switch (rule.kind) {
    case 'time_window': {
      const { start, end } = rule.params as TimeWindowParams;
      return `No-logging window ${start}–${end}`;
    }
    case 'daily_cap': {
      const { maxCalories = 0, maxEntries = 0 } = rule.params as DailyCapParams;
      const parts: string[] = [];
      if (maxCalories > 0) parts.push(`${maxCalories} kcal`);
      if (maxEntries > 0) parts.push(`${maxEntries} entries`);
      return `Daily cap: ${parts.join(' + ') || 'not set'}`;
    }
    case 'keyword': {
      const { keyword } = rule.params as KeywordParams;
      return `Watch for "${keyword}"`;
    }
  }
}
