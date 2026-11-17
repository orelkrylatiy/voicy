# Voicey VPS deployment

The GitHub workflow uploads source to the shared Deployment Manager. The manager installs the pinned Humanizer dependency into each release's `vendor/` directory, switches `current`, and restarts `voicy.service`.

Install `deploy/deploy-manager.toml` at `/etc/deploy-manager/projects/voicy.toml`, `deploy/voicy.service` at `/etc/systemd/system/voicy.service`, and `deploy/voicy.sudoers` at `/etc/sudoers.d/voicy-deploy` with mode `0440`. Initialize with `deploy-manager init voicy` as the `deploy` user.

Place the real Telegram token, owner IDs, and OpenAI key only in `/var/www/projects/voicy/shared/.env` (mode `0600`, owned by `deploy`). Enable the service and set the GitHub variable `ENABLE_VPS_DEPLOY=true` only after that configuration exists and validates. Never store the secrets in Git.
