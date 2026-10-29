#!/usr/bin/env bash
# ==============================================================================
# GitHub Auto-Sync Script for Car Hauling Dispatch Hub
# Run manually, or configure as a cron job / GitHub Webhook listener.
# ==============================================================================

set -e

REPO_DIR="/opt/dispatch-hub"
cd "$REPO_DIR"

echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] Checking for GitHub updates..."

# If inside git repo, pull latest changes
if [ -d ".git" ]; then
    git pull origin main || echo "[WARN] Git pull failed or no remote set."
fi

# Run python sync to hot-reload parameters into n8n and config.json
python3 "$REPO_DIR/scripts/sync_github_config.py"

echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] Sync finished."
