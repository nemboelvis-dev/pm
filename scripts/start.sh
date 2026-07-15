#!/usr/bin/env sh
set -eu

project_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

if [ ! -f "$project_root/.env" ]; then
    echo "Missing .env. Copy .env.example to .env and set OPENROUTER_API_KEY." >&2
    exit 1
fi

docker compose --project-directory "$project_root" up --build --detach
