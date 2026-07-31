#!/bin/sh
set -eu

docker-compose exec mongo sh -c 'exec mongosh "$MONGO_DATABASE" --username "$MONGO_INITDB_ROOT_USERNAME" --password "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin --eval "$1"' sh \
  'db.notebooks.find({}, {notebook: 0}).sort({date: -1}).forEach(printjson)'
