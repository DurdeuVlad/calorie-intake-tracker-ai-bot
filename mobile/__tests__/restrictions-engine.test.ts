import { describeRule, evaluate } from '../src/restrictions/engine';
import { dayKey, MemoryRestrictionStore } from '../src/restrictions/store';
import type { EvaluationContext, Rule } from '../src/restrictions/types';

function ctx(overrides: Partial<EvaluationContext> = {}): EvaluationContext {
  return {
    now: new Date(2026, 9, 12, 22, 30), // Mon Oct 12 2026, 22:30 local
    text: '',
    caloriesToday: 0,
    entriesToday: 0,
    ...overrides,
  };
}

function rule(overrides: Partial<Rule> & Pick<Rule, 'kind' | 'params'>): Rule {
  return { id: 'r1', enabled: true, ...overrides };
}

describe('evaluate — time_window', () => {
  const window = rule({
    kind: 'time_window',
    params: { start: '21:00', end: '07:00' }, // overnight window
  });

  it('nudges inside an overnight window (late side)', () => {
    expect(evaluate([window], ctx())).toHaveLength(1);
  });

  it('nudges inside an overnight window (early side)', () => {
    const nudges = evaluate([window], ctx({ now: new Date(2026, 9, 12, 6, 15) }));
    expect(nudges).toHaveLength(1);
    expect(nudges[0].kind).toBe('time_window');
    expect(nudges[0].ruleId).toBe('r1');
  });

  it('does not nudge outside the window', () => {
    expect(evaluate([window], ctx({ now: new Date(2026, 9, 12, 12, 0) }))).toHaveLength(0);
  });

  it('handles same-day windows and boundary edges', () => {
    const lunch = rule({
      kind: 'time_window',
      params: { start: '12:00', end: '14:00' },
    });
    expect(evaluate([lunch], ctx({ now: new Date(2026, 9, 12, 11, 59) }))).toHaveLength(0);
    expect(evaluate([lunch], ctx({ now: new Date(2026, 9, 12, 12, 0) }))).toHaveLength(1);
    expect(evaluate([lunch], ctx({ now: new Date(2026, 9, 12, 14, 0) }))).toHaveLength(0);
  });

  it('never nudges for a degenerate or malformed window', () => {
    const empty = rule({ kind: 'time_window', params: { start: '08:00', end: '08:00' } });
    const bad = rule({ kind: 'time_window', params: { start: '25:00', end: 'nope' } });
    expect(evaluate([empty, bad], ctx())).toHaveLength(0);
  });
});

describe('evaluate — daily_cap', () => {
  const cap = rule({
    kind: 'daily_cap',
    params: { maxCalories: 2000, maxEntries: 5 },
  });

  it('does not nudge under both caps', () => {
    expect(evaluate([cap], ctx({ caloriesToday: 1500, entriesToday: 3 }))).toHaveLength(0);
  });

  it('nudges when the calorie cap is reached', () => {
    const nudges = evaluate([cap], ctx({ caloriesToday: 2000, entriesToday: 2 }));
    expect(nudges).toHaveLength(1);
    expect(nudges[0].message).toContain('2000');
  });

  it('nudges when the entry cap is reached', () => {
    expect(evaluate([cap], ctx({ caloriesToday: 100, entriesToday: 5 }))).toHaveLength(1);
  });

  it('supports a calories-only cap', () => {
    const caloriesOnly = rule({ kind: 'daily_cap', params: { maxCalories: 500 } });
    expect(evaluate([caloriesOnly], ctx({ caloriesToday: 499, entriesToday: 99 }))).toHaveLength(
      0,
    );
    expect(evaluate([caloriesOnly], ctx({ caloriesToday: 500 }))).toHaveLength(1);
  });

  it('treats missing/zero caps as unset', () => {
    const unset = rule({ kind: 'daily_cap', params: {} });
    expect(evaluate([unset], ctx({ caloriesToday: 99999, entriesToday: 999 }))).toHaveLength(0);
  });
});

describe('evaluate — keyword', () => {
  const watch = rule({ kind: 'keyword', params: { keyword: 'chocolate' } });

  it('nudges on a case-insensitive substring match', () => {
    const nudges = evaluate([watch], ctx({ text: 'a bar of Chocolate with coffee' }));
    expect(nudges).toHaveLength(1);
    expect(nudges[0].message).toContain('chocolate');
  });

  it('does not nudge when the text does not contain the keyword', () => {
    expect(evaluate([watch], ctx({ text: 'salad and soup' }))).toHaveLength(0);
  });

  it('does not nudge for voice notes (empty text) or blank keywords', () => {
    expect(evaluate([watch], ctx())).toHaveLength(0);
    const blank = rule({ kind: 'keyword', params: { keyword: '   ' } });
    expect(evaluate([blank], ctx({ text: 'anything' }))).toHaveLength(0);
  });
});

describe('evaluate — combinations and disabled rules', () => {
  it('returns one nudge per triggered rule, in rule order', () => {
    const rules: Rule[] = [
      rule({ id: 'a', kind: 'keyword', params: { keyword: 'cake' } }),
      rule({ id: 'b', kind: 'daily_cap', params: { maxCalories: 100 } }),
      rule({ id: 'c', kind: 'time_window', params: { start: '00:00', end: '23:59' } }),
    ];
    const nudges = evaluate(
      rules,
      ctx({ text: 'big slice of cake', caloriesToday: 150, now: new Date(2026, 9, 12, 12, 0) }),
    );
    expect(nudges.map((n) => n.ruleId)).toEqual(['a', 'b', 'c']);
  });

  it('skips disabled rules', () => {
    const rules: Rule[] = [
      rule({ id: 'off', kind: 'keyword', params: { keyword: 'cake' }, enabled: false }),
      rule({ id: 'on', kind: 'keyword', params: { keyword: 'cake' } }),
    ];
    const nudges = evaluate(rules, ctx({ text: 'cake' }));
    expect(nudges.map((n) => n.ruleId)).toEqual(['on']);
  });

  it('returns nothing when no rules exist', () => {
    expect(evaluate([], ctx({ text: 'cake', caloriesToday: 9999 }))).toEqual([]);
  });
});

describe('describeRule', () => {
  it('describes each kind for the list UI', () => {
    expect(
      describeRule(rule({ kind: 'time_window', params: { start: '21:00', end: '07:00' } })),
    ).toBe('No-logging window 21:00–07:00');
    expect(
      describeRule(rule({ kind: 'daily_cap', params: { maxCalories: 2000, maxEntries: 5 } })),
    ).toBe('Daily cap: 2000 kcal + 5 entries');
    expect(describeRule(rule({ kind: 'keyword', params: { keyword: 'soda' } }))).toBe(
      'Watch for "soda"',
    );
  });
});

describe('dayKey + MemoryRestrictionStore', () => {
  it('formats a local calendar-day key', () => {
    expect(dayKey(new Date(2026, 0, 5, 9, 30))).toBe('2026-01-05');
    expect(dayKey(new Date(2026, 11, 31, 23, 59))).toBe('2026-12-31');
  });

  it('accumulates intake per day and round-trips rules', async () => {
    const store = new MemoryRestrictionStore();
    const r = rule({ kind: 'keyword', params: { keyword: 'soda' } });

    await store.saveRule(r);
    expect(await store.listRules()).toEqual([r]);

    await store.addIntake('2026-10-12', 300, 1);
    await store.addIntake('2026-10-12', 150, 2);
    await store.addIntake('2026-10-13', 50, 1);
    expect(await store.getIntake('2026-10-12')).toEqual({ calories: 450, entries: 3 });
    expect(await store.getIntake('2026-10-13')).toEqual({ calories: 50, entries: 1 });
    expect(await store.getIntake('2026-10-14')).toEqual({ calories: 0, entries: 0 });

    await store.deleteRule(r.id);
    expect(await store.listRules()).toEqual([]);
  });
});
