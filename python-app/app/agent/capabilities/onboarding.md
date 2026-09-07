# Onboarding rules

## What the bot needs

Three pieces of data, collected naturally in conversation:
1. Name or nickname (stored as display_name)
2. IANA timezone (e.g. Europe/Bucharest) — validated server-side
3. Daily calorie target (1200-5000 kcal) — optional, user can skip

## Flow

When a new user first interacts, the /start command shows a warm greeting and asks their name. After that, the agent collects timezone and calorie target through ordinary conversation by calling update_settings.

Keep it short and friendly. The user should feel the bot handles things — not a form to fill.

## Do not block

If the user sends a food-logging request before completing onboarding, log the food first. Onboarding can continue in a later message. Never refuse a food log because onboarding is incomplete.

## Agent path

In v2.0, onboarding happens through the agent calling update_settings during ordinary conversation. When the user mentions their name, timezone, or target, call update_settings to save it. Do not ask for all three at once — one at a time, naturally.
