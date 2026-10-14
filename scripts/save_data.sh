#!/usr/bin/env bash
# Commits post history and the video queue back to the repository.
set -e
git config user.name "mehr-bot"
git config user.email "mehr-bot@users.noreply.github.com"
git add data/
git diff --cached --quiet && exit 0
git commit -m "Post ma'lumotlari yangilandi"
for i in 1 2 3; do git pull --rebase && git push && exit 0; sleep 5; done
exit 1
