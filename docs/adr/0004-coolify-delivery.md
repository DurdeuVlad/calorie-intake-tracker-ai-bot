# ADR 0004: Deferred Coolify deployment from protected master

**Status:** Accepted

GitHub Actions validates pull requests and `master` without deployment. Coolify remains disconnected until full-system acceptance, then builds/deploys the protected `master` branch. Coolify stores runtime secrets and mounts persistent database storage; no secret is baked into images or committed to Git.
