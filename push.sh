#!/usr/bin/env bash
# Push to main, auto-resolving conflicts caused by the scheduled scraper
# by keeping our local versions of data files.
set -e

if git push origin main 2>/dev/null; then
    echo "Pushed."
else
    echo "Push rejected — scraper committed in the meantime. Rebasing..."
    git pull --rebase -X theirs origin main
    git push origin main
    echo "Pushed."
fi
