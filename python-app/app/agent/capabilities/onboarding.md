# Onboarding rules

## Timezone setup

Guide the user to send their IANA timezone (e.g. "Europe/Bucharest"). The server validates it against the IANA timezone database.

## Calorie target setup

After the timezone is set, ask for a daily calorie target (1200-5000 kcal). The user may skip this step and set it later.

## Agent path

In v2.0, onboarding happens through the agent calling `update_settings` during ordinary conversation. The model should proactively ask for missing timezone or calorie target when the user first interacts, then call `update_settings` to save them.

## Do not block

If the user sends a food-logging request before completing onboarding, log the food first. Onboarding can continue in a later message.
