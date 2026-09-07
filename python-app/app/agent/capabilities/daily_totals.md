# Daily totals and meal listing

## Daily total question

For daily totals such as "cate calorii azi?", "total azi?", or "how many calories today?", always call `get_today_summary`. Never call `search_entries` for a daily-total question.

State calories and meal count for totals, and mention the target when configured.

## Weekly summary

For weekly questions such as "cate calorii am facut saptamana asta?", "totalul pe saptamana", or "how did last week go?", call `get_weekly_summary`. It returns per-day totals for the seven days ending on the reference date (default: today), the weekly total, the daily average, and the target. The optional `date` argument sets the reference day and accepts today, yesterday, ieri, or an ISO date; it must not be in the future.

Present the weekly total, the daily average, and call out the highest and lowest days. Mention the target when configured. Do not fabricate per-day numbers — use the values returned by the tool.

## Meal listing

For "ce am mancat azi", "arata-mi mesele de azi", "what did I eat today", or any request to list meals, call `search_entries` with no query or date filters and list the returned entries directly. Do not return only a summary.

## Food history search

For "when did I last eat X?", "how many times have I had Y?", or any history question spanning more than today, call `search_food_history` with the food term. It returns the count, first and last eaten timestamps, average calories, and the five most recent matching entries. Present the last-eaten date and the count clearly; mention the average calories when useful.

## Do not mutate for reads

Do not resolve nutrition or mutate the journal for any of these read-only questions.
