# Product brief

## Problem

The existing n8n automation has become difficult to operate and change. Household users need a quick way to record what they ate without losing privacy or creating duplicate records.

## Users

Allowlisted members of one household, interacting only through one Telegram bot.

## Goals

- Capture meals from text, voice, photos, and documents.
- Keep a trustworthy, editable daily food journal with nutrition provenance.
- Deliver useful daily totals without manual spreadsheet work.
- Make operation reproducible on a private Coolify homelab.

## Non-goals

- Public signup, billing, social features, medical diagnosis, or dietary advice.
- Retention of original uploaded media.
- Exact nutritional truth when the source is an estimate.

## Core use cases

1. A user sends “two eggs and toast” and gets a concise saved-entry confirmation.
2. A user sends a voice note, food photo, or label/document; the bot extracts a proposed meal and safely asks for clarification when needed.
3. A user asks what they ate today or searches for a food/date range.
4. A user corrects or deletes one of their own entries.
5. A user configures timezone, calorie target, and report preferences.
6. The bot sends one morning and one evening report in the user's local timezone.
