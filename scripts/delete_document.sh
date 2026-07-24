#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 DOCUMENT_ID" >&2
  exit 2
fi

docker compose exec -e DOCUMENT_ID="$1" mongo mongosh flaskdb --quiet --eval '
  if (!ObjectId.isValid(process.env.DOCUMENT_ID)) { print("Invalid document ID"); quit(2); }
  const result = db.notebooks.deleteOne({_id: ObjectId.createFromHexString(process.env.DOCUMENT_ID)});
  if (!result.deletedCount) { print("Document not found"); quit(1); }
  print(`Deleted document ${process.env.DOCUMENT_ID}`);
'
