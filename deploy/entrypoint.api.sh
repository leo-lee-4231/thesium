#!/bin/sh
set -eu

# Migrations and idempotent seed run before the process starts.
alembic upgrade head
python -m app.scripts.seed

exec "$@"