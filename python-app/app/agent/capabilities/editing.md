# Editing, moving, and deleting entries

## Search-before-mutate

Before EDIT, MOVE, or DELETE, call `search_entries` using the food text and the requested date or date range. If exactly one entry matches, mutate it immediately.

## EDIT is absolute, not delta

The calories field of an EDIT is always the new absolute total, never a delta. After finding a gin tonic logged as 1 kcal, "do 150 kcal" means EDIT it with calories 150, not 1, 2, or 151.

## Duplicate detection

"noteaza doar o data", "am mancat doar unul", "only once", and "I ate only one" are correction requests: find the duplicate and delete the accidental newer copy, never create another meal.

## Clarification

Ask one short clarification only when multiple plausible entries remain. Do not clarify facts already stated by the user.

## Undo

For a standalone "undo", "anuleaza", or "anulează", call `undo_last_change` immediately. It reverses the most recent change set when still within ten minutes.

## Batch behavior

Mixed batches are allowed. After the tool returns, write a receipt listing every success and every failure separately. Successful actions remain applied when another action fails. Do NOT resend a batch that had any successful actions — those are already committed and resending would duplicate them. If every action in a batch failed, you may retry once with corrected arguments.
