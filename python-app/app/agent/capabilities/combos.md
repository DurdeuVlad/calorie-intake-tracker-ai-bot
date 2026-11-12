# Combo meal rules

## Combo-meal-is-one-CREATE

When the user describes several foods eaten together as one meal (a combo, a "meniu", a mixed order from one place) and gives, or agrees to, a single rough total for the whole thing, create exactly one CREATE action for the whole meal using that total as calories, `nutritionSource: ai_estimate`, `nutritionConfidence: estimate`, and `unit: unspecified`.

Do not try to split the total across per-item entries and do not require grams for the individual components.

## Ask once rule

A multi-item order from a named restaurant or brand (e.g. "10 hot wings, medium fries and garlic sauce, all from KFC") is NOT a case for asking: search_web each item (brand plus item), then log one CREATE per item with its own looked-up calories, covering the full quantity stated. Never ask the user for a total they cannot know.

Ask once only when an unbranded combo or mixed meal has no portion, no total calories, and nothing you can look up item by item. Then ask for a rough total or breakdown.

If the user's next message does not supply new numeric detail, declines to give one, or tells you to just estimate or handle it yourself, you must act immediately on the best number available: their stated total if any, otherwise your own transparent estimate. Asking again is not allowed.

## Multi-meal messages

If a message names several distinct meals (not a combo), send several CREATE actions together in one `apply_journal_actions` call.
