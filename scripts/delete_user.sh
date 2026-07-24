#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 USERNAME" >&2
  exit 2
fi

docker compose exec -e TARGET_USERNAME="$1" mongo mongosh flaskdb --quiet --eval '
  const user = db.users.findOne({username: process.env.TARGET_USERNAME});
  if (!user) { print("User not found"); quit(1); }
  const documents = db.notebooks.deleteMany({author: user._id.toString()});
  db.users.deleteOne({_id: user._id});
  print(`Deleted user ${user.username} and ${documents.deletedCount} document(s)`);
'
