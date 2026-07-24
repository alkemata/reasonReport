#!/bin/sh
set -eu

docker-compose exec mongo mongosh flaskdb --eval \
  'db.notebooks.find({}, {notebook: 0}).sort({date: -1}).forEach(printjson)'
