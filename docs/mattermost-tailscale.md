# Mattermost over Tailscale

Mattermost is deliberately bound to `127.0.0.1:8065`. Do not expose that port through a router, reverse proxy, or Coolify public domain.

1. Set `MATTERMOST_PUBLIC_URL` to the stable MagicDNS HTTPS name selected for this host.
2. Start the Compose stack, complete Mattermost's local administrator setup, create the household team, enable bot-account creation, and create the food-journal bot.
3. Record the bot user ID and personal access token outside Git. Set `MATTERMOST_FRONTEND_ENABLED=true`, `MATTERMOST_BOT_USER_ID`, `MATTERMOST_BOT_TOKEN`, and the explicit `ALLOWED_MATTERMOST_USER_IDS` allowlist.
4. On the host, publish the local service only to the Tailnet: `tailscale serve --bg 8065`. Restrict the hostname with Tailnet ACLs.
5. Each existing user sends `/link` to Telegram and sends the returned `link CODE` command in a direct message to the Mattermost bot. Codes expire after ten minutes and can be used once.

The app subscribes to the authenticated Mattermost WebSocket and ignores channel posts, bot posts, and non-allowlisted accounts. The Mattermost server and its PostgreSQL database use dedicated volumes; back them up independently from the journal database.
