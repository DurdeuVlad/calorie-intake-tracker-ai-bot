# Aliases — personal food shorthand

## When to load

Load this when the user defines a personal shorthand for a food ("cafea means coffee with milk, 30ml"), asks you to remember a nickname, or when an incoming message uses a word that might be a personal alias.

## Tools

- `save_alias(alias, canonicalName, caloriesPer100g?, fixedCalories?)` — create or update a personal alias. Provide either `caloriesPer100g` or `fixedCalories`, not both. The server stores the alias scoped to the current user only.
- `resolve_alias(alias)` — look up a previously saved alias. Returns `resolved: false` when no alias matches. Matching is case-insensitive.

## How to use aliases

1. When the user says "remember that X means Y" or "X is my shorthand for Y", call `save_alias`.
2. Before resolving nutrition for a short or ambiguous food word, call `resolve_alias` to check whether the user has a personal mapping. If resolved, use the `canonicalName` (and the embedded nutrition shortcut if present) instead of treating the alias as a free-text food.
3. Aliases are per-user. Another user's aliases are never visible.
4. An alias without a nutrition shortcut still substitutes the canonical name; the model still resolves calories through the normal nutrition path.
5. Do not invent aliases. Only save one when the user explicitly asks.

## Receipts

After `save_alias`, confirm briefly: "Saved alias 'cafea' → 'coffee with milk, 30ml'." Do not list unrelated aliases.
