#!/bin/bash

set -euo pipefail

if [ -z $'(ls -A migrations/versions/)']; then
	echo "No migrations file were found. Do you forget to commit them?"
	exit 1
fi

echo '[ALEMBIC|ENTRYPOINT]: Applying database migrations...'
alembic upgrade head
echo '[ALEMBIC|ENTRYPOINT]: Database migrations completed.'
