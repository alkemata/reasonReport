#!/usr/bin/env python3
"""Issue, list, or revoke hashed MCP bearer tokens."""

import argparse
import os
import secrets
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bson import ObjectId
from pymongo import MongoClient

source_app = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(source_app if source_app.exists() else Path("/app")))
from reasonreport_mcp.tokens import TOKEN_PREFIX, token_digest  # noqa: E402

SCOPES = {"documents:read", "documents:write", "documents:delete"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    issue = sub.add_parser("issue")
    issue.add_argument("username")
    issue.add_argument("--name", required=True)
    issue.add_argument("--days", type=int, default=90)
    issue.add_argument("--scopes", nargs="+", choices=sorted(SCOPES), default=sorted(SCOPES))
    sub.add_parser("list")
    revoke = sub.add_parser("revoke")
    revoke.add_argument("token_id")
    args = parser.parse_args()
    db = MongoClient(os.environ["MONGO_URI"]).get_default_database()
    pepper = os.environ["MCP_TOKEN_PEPPER"]
    now = datetime.now(timezone.utc)
    if args.command == "issue":
        if not 1 <= args.days <= 365:
            parser.error("--days must be between 1 and 365")
        user = db.users.find_one({"username_normalized": args.username.strip().casefold(), "status": "active"})
        if not user:
            parser.error("active user not found")
        raw = TOKEN_PREFIX + secrets.token_urlsafe(48)
        result = db.mcp_tokens.insert_one({
            "token_hash": token_digest(raw, pepper), "user_id": user["_id"], "name": args.name[:100],
            "scopes": args.scopes, "created_at": now, "expires_at": now + timedelta(days=args.days),
            "last_used_at": None, "revoked_at": None,
        })
        print(f"Token ID: {result.inserted_id}\nBearer token (shown once): {raw}")
    elif args.command == "list":
        for item in db.mcp_tokens.find({}, {"token_hash": 0}).sort("created_at", -1):
            print(item)
    else:
        if not ObjectId.is_valid(args.token_id):
            parser.error("invalid token ID")
        result = db.mcp_tokens.update_one({"_id": ObjectId(args.token_id), "revoked_at": None},
                                          {"$set": {"revoked_at": now}})
        print("revoked" if result.modified_count else "not found or already revoked")


if __name__ == "__main__":
    main()
