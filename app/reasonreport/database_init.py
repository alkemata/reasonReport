"""MongoDB schema and index initialization for ReasonReport.

Run :func:`initialize_database` once when an application process is started.  In
particular, request handlers must not create indexes: index builds take locks and
are an operational concern rather than part of serving a request.
"""

from pymongo import ASCENDING, DESCENDING
from pymongo.errors import CollectionInvalid


VISIBILITIES = ["private", "restricted", "public"]


def _object_id():
    return {"bsonType": "objectId"}


COLLECTION_VALIDATORS = {
    "users": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["username", "username_normalized", "status", "created_at"],
            "properties": {
                "username": {"bsonType": "string", "minLength": 3},
                "username_normalized": {"bsonType": "string", "minLength": 3},
                "status": {"enum": ["active", "disabled", "pending"]},
                "created_at": {"bsonType": "date"},
            },
        }
    },
    "notebooks": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": [
                "owner_id", "title", "slug", "created_at", "updated_at",
                "visibility", "allowed_user_ids", "topic_ids", "revision",
            ],
            "properties": {
                "owner_id": _object_id(),
                "title": {"bsonType": "string"},
                "slug": {"bsonType": "string"},
                "created_at": {"bsonType": "date"},
                "updated_at": {"bsonType": "date"},
                "visibility": {"enum": VISIBILITIES},
                "allowed_user_ids": {"bsonType": "array", "items": _object_id()},
                "topic_ids": {"bsonType": "array", "items": _object_id()},
                "revision": {"bsonType": "int", "minimum": 1},
            },
        }
    },
    "topics": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["name", "name_normalized", "created_at"],
            "properties": {
                "name": {"bsonType": "string"},
                "name_normalized": {"bsonType": "string"},
                "created_at": {"bsonType": "date"},
            },
        }
    },
    "audit_events": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["occurred_at", "event_type"],
            "properties": {
                "occurred_at": {"bsonType": "date"},
                "event_type": {"bsonType": "string"},
                "actor_id": _object_id(),
            },
        }
    },
    "presence_sessions": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["user_id", "expires_at"],
            "properties": {"user_id": _object_id(), "expires_at": {"bsonType": "date"}},
        }
    },
    "editor_sessions": {
        "$jsonSchema": {"bsonType": "object", "required": ["user_id", "expires_at", "delete_at"],
                        "properties": {"user_id": _object_id(), "expires_at": {"bsonType": "date"},
                                       "delete_at": {"bsonType": "date"}}}
    },
    "editor_launches": {
        "$jsonSchema": {"bsonType": "object", "required": ["user_id", "expires_at"],
                        "properties": {"user_id": _object_id(), "expires_at": {"bsonType": "date"}}}
    },
    "mcp_tokens": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["token_hash", "user_id", "name", "scopes", "created_at", "expires_at"],
            "properties": {
                "token_hash": {"bsonType": "string"},
                "user_id": _object_id(),
                "name": {"bsonType": "string"},
                "scopes": {"bsonType": "array", "items": {"bsonType": "string"}},
                "created_at": {"bsonType": "date"},
                "expires_at": {"bsonType": "date"},
            },
        }
    },
}


INDEXES = {
    "users": [
        ([('username_normalized', ASCENDING)], {"name": "uq_users_username_normalized", "unique": True}),
        ([('status', ASCENDING), ('created_at', DESCENDING)], {"name": "ix_users_status_created"}),
    ],
    "notebooks": [
        ([('slug', ASCENDING)], {"name": "uq_notebooks_slug", "unique": True}),
        ([('owner_id', ASCENDING), ('updated_at', DESCENDING)], {"name": "ix_notebooks_owner_updated"}),
        ([('visibility', ASCENDING), ('updated_at', DESCENDING)], {"name": "ix_notebooks_visibility_updated"}),
        ([('allowed_user_ids', ASCENDING)], {"name": "ix_notebooks_allowed_users"}),
        ([('topic_ids', ASCENDING)], {"name": "ix_notebooks_topics"}),
    ],
    "audit_events": [
        ([('occurred_at', DESCENDING), ('event_type', ASCENDING)], {"name": "ix_audit_time_type"}),
    ],
    "presence_sessions": [
        ([('expires_at', ASCENDING)], {"name": "ttl_presence_expiry", "expireAfterSeconds": 0}),
    ],
    "editor_sessions": [
        ([('delete_at', ASCENDING)], {"name": "ttl_editor_session", "expireAfterSeconds": 0}),
    ],
    "editor_launches": [
        ([('expires_at', ASCENDING)], {"name": "ttl_editor_launch", "expireAfterSeconds": 0}),
    ],
    "mcp_tokens": [
        ([('token_hash', ASCENDING)], {"name": "uq_mcp_token_hash", "unique": True}),
        ([('user_id', ASCENDING), ('created_at', DESCENDING)], {"name": "ix_mcp_user_created"}),
        ([('expires_at', ASCENDING)], {"name": "ttl_mcp_token_expiry", "expireAfterSeconds": 0}),
    ],
}


def initialize_database(db):
    """Idempotently create collections, validators, and application indexes."""
    existing = set(db.list_collection_names())
    for name, validator in COLLECTION_VALIDATORS.items():
        if name not in existing:
            try:
                db.create_collection(name, validator=validator)
            except CollectionInvalid:  # another process won the startup race
                pass
        db.command(
            "collMod", name, validator=validator,
            validationLevel="moderate", validationAction="error",
        )
    for collection_name, definitions in INDEXES.items():
        collection = db[collection_name]
        for keys, options in definitions:
            collection.create_index(keys, **options)
