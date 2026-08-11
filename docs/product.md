# Product Vision & Capabilities

## The Problem

Tracking calorie intake and macro nutrition is one of the most effective tools for health management. However, almost all existing solutions fail users for three primary reasons:

1. **Friction Fatigue**: Traditional mobile apps force users to search millions of crowdsourced, inaccurate database items, weigh every item, and tap through multiple UI screens per meal. Most users abandon logging within 14 days.
2. **Privacy Risks**: Commercial nutrition applications track, analyze, and sell personal dietary and health data to advertisers. They also retain uploaded meal photos and voice recordings indefinitely on proprietary servers.
3. **Automated Workflow Fragility**: Low-code automation platforms (like n8n or Make) are difficult to maintain, fail unpredictably on complex multi-item meals, lack transactional rollback capability, and duplicate entries on network retries.

---

## The Solution: Food Journal Messaging Bot

A self-hosted, private messaging bot designed to turn natural human communication into a accurate, database-backed food journal.

- **Conversation First**: Speak, type, or photograph what you ate in plain English, Romanian, or mixed language.
- **AI Reasoning + Validated Transactional Execution**: OpenAI handles natural language and image processing, while strict Spring Boot application code enforces ownership, validation, macro calculations, and database mutations.
- **Private & Multi-Frontend**: Chat seamlessly over **Telegram** or **Mattermost (over Tailscale)**.

---

## Core Capabilities & Features

### 1. Flexible Multi-Modal Logging
- **Text Messages**: Log simple or complex multi-item meals (e.g., *"2 scrambled eggs with butter, sourdough toast, and a small cappuccino"*).
- **Voice Notes**: Send voice messages in English or Romanian; automatically transcribed via OpenAI Audio and converted into structured food entries.
- **Photos & Documents**: Send pictures of meals, restaurant menus, or nutrition facts labels; extracted via vision AI into validated journal entries.

### 2. Live Pinned Status & Scheduled Reports
- **Pinned Daily Status**: Automatically maintains a live, pinned Telegram/Mattermost message showing today's eaten items, calorie total, remaining calorie budget, and macro totals.
- **Local Timezone Daily Reports**: Delivers morning summaries (setting up daily targets) and evening summaries (reviewing daily consumption) based on each user's configured IANA timezone.

### 3. Smart Nutrition Lookup & Web Tools
- **Open Food Facts API**: Resolves official product barcode and branded food data.
- **SearxNG Web Search**: Performs self-hosted web searches for restaurant menus and meal nutrition.
- **Browserless Scraping**: Fetches web page content for detailed recipe/nutrition extraction.
- **Provenanced Sources**: Every nutrition entry is transparently labelled (`OFFICIAL_SOURCE`, `PRIVATE_RECORD`, `MANUAL`, or `AI_ESTIMATE`).

### 4. Reversible 10-Minute Undo
- Made a typo or logged something by accident? Send `/undo` or tell the bot *"undo that"*.
- Every message mutation produces a snapshot change set (`JournalChangeSet`) that can be safely reverted within 10 minutes.

---

## User Personas & Scope

- **Primary Users**: Members of a household using Telegram or private Mattermost for daily chat.
- **Non-Goals**:
  - Public multi-tenant commercial SaaS with billing.
  - Social media feeds or community meal sharing.
  - Medical diagnosis or dietary treatment advice.
  - Long-term storage of raw audio, image, or document files.

