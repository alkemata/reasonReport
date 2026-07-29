#!/bin/sh
set -eu

if [ "${1:-}" != "--yes" ] || [ "$#" -ne 1 ]; then
  echo "Usage: $0 --yes" >&2
  echo "This permanently deletes every user and notebook." >&2
  exit 2
fi

docker-compose exec mongo mongosh flaskdb --quiet --eval '
  const notebooks = db.notebooks.deleteMany({});
  const users = db.users.deleteMany({});
  print(`Deleted ${users.deletedCount} user(s) and ${notebooks.deletedCount} notebook(s)`);
'
