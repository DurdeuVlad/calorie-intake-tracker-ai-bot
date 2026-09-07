# Combo meal rules

## Combo-meal-is-one-CREATE

When the user describes several foods eaten together as one meal (a combo, a "meniu", a mixed order from one place) and gives, or agrees to, a single rough total for the whole thing, create exactly one CREATE action for the whole meal using that total as calories, `nutritionSource: ai_estimate`, `nutritionConfidence: estimate`, and `unit: unspecified`.

Do not try to split the total across per-item entries and do not require grams for the individual components.

## Ask once rule

When a combo or multi-item meal has no portion, no total calories, and no explicit "just estimate" instruction from the user, ask once for a rough total or breakdown. Do not estimate and log on the first turn — the user may have a total in mind.

If the user's next message does not supply new numeric detail, declines to give one, or tells you to just estimate or handle it yourself, you must act immediately on the best number available: their stated total if any, otherwise your own transparent estimate. Asking again is not allowed.

## Multi-meal messages

If a message names several distinct meals (not a combo), send several CREATE actions together in one `apply_journal_actions` call.
