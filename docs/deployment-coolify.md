# Deferred Coolify deployment

Coolify is deliberately disconnected during development. This document becomes actionable only after the complete product (text, voice, images, documents, nutrition, reports, and operations) passes final acceptance.

1. Connect Coolify to the Git repository and deploy the protected `master` branch only after final acceptance is green.
2. Configure a PostgreSQL service or private database with a persistent volume and a backup policy.
3. Add all variables in [configuration](configuration.md) as Coolify secrets/environment values.
4. Publish the application through HTTPS, then register the Telegram webhook at the documented endpoint using the same webhook secret.
5. Verify health, Flyway migration completion, one allowlisted `/start`, and one report schedule before cutover.

Coolify owns runtime secrets and persistent volumes. The application container must be stateless. Roll back application images only after confirming database-migration compatibility; never roll back a migration by deleting production data.
