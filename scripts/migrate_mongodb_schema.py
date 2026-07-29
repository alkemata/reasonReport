#!/usr/bin/env python3
"""Idempotently migrate legacy ReasonReport MongoDB documents."""

import os
from datetime import datetime, timezone

from bson import ObjectId
from pymongo import MongoClient


def _object_id(value):
    if isinstance(value, ObjectId):
        return value
    return ObjectId(value) if ObjectId.is_valid(str(value)) else None


def migrate(db):
    """Migrate legacy fields without changing already-migrated values."""
    now = datetime.now(timezone.utc)
    for user in db.users.find({}):
        changes = {}
        changes.setdefault("username_normalized", user.get("username", "").strip().casefold())
        changes.setdefault("status", "active")
        changes.setdefault("created_at", user.get("created_at") or now)
        db.users.update_one(
            {"_id": user["_id"]},
            {"$set": {key: value for key, value in changes.items() if key not in user}},
        )

    for notebook in db.notebooks.find({}):
        created_at = notebook.get("created_at") or notebook.get("date") or now
        owner_id = _object_id(notebook.get("owner_id") or notebook.get("author"))
        visibility = notebook.get("visibility")
        if visibility not in {"private", "restricted", "public"}:
            # Missing visibility is deliberately private; only an explicit legacy
            # true value is evidence that a notebook was published.
            visibility = "public" if notebook.get("is_public") is True else "private"
        defaults = {
            "title": notebook.get("title") or "Untitled",
            "slug": notebook.get("slug") or f"notebook-{notebook['_id']}",
            "created_at": created_at,
            "updated_at": notebook.get("updated_at") or created_at,
            "visibility": visibility,
            "allowed_user_ids": [],
            "topic_ids": [],
            "revision": 1,
        }
        if owner_id is not None:
            defaults["owner_id"] = owner_id
        db.notebooks.update_one(
            {"_id": notebook["_id"]},
            {
                "$set": {key: value for key, value in defaults.items() if key not in notebook},
                "$unset": {"author": "", "date": "", "is_public": ""},
            },
        )


if __name__ == "__main__":
    client = MongoClient(os.environ.get("MONGO_URI", "mongodb://mongo:27017/flaskdb"))
    migrate(client.get_default_database())
