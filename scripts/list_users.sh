#!/bin/sh
set -eu

docker-compose exec mongo mongosh flaskdb --eval \
  'db.users.find({}, {password: 0}).sort({username: 1}).forEach(printjson)'
