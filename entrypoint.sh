#!/bin/bash

echo "Waiting for database..."
if [ -f "src/manage.py" ]; then
    echo "manage.py found, running migrations..."
    python src/manage.py migrate
else
    echo "manage.py not found. Skipping migrations for now."
fi
exec "$@"