"""MongoDB operations exposed by MCP, isolated for validation and testing."""

from datetime import datetime, timezone
import re

import nbformat
from bson import ObjectId
from pymongo import ReturnDocument
from slugify import slugify


VALID_VISIBILITIES = {"private", "public"}


class KnowledgeService:
    def __init__(self, database):
        self.db = database

    @staticmethod
    def _owner_query(user_id: str):
        values = [user_id]
        if ObjectId.is_valid(user_id):
            values.append(ObjectId(user_id))
        return {"$in": values}

    def _visible_query(self, user_id: str):
        identities = self._owner_query(user_id)["$in"]
        return {"$or": [
            {"owner_id": {"$in": identities}},
            {"visibility": "public"},
            {"allowed_user_ids": {"$in": identities}},
        ]}

    def _owned_document(self, document_id: str, user_id: str):
        if not ObjectId.is_valid(document_id):
            raise ValueError("Invalid document_id")
        document = self.db.notebooks.find_one(
            {"_id": ObjectId(document_id), "owner_id": self._owner_query(user_id)}
        )
        if not document:
            raise PermissionError("Document not found or not owned by this token's user")
        return document

    @staticmethod
    def _metadata(document):
        return {
            "id": str(document["_id"]),
            "title": document.get("title", ""),
            "slug": document.get("slug", ""),
            "author_id": str(document.get("owner_id", "")),
            "visibility": document.get("visibility", "private"),
            "tags": document.get("tags", []),
            "summary": document.get("summary", ""),
            "created_at": document.get("created_at").isoformat() if document.get("created_at") else None,
            "updated_at": document.get("updated_at").isoformat() if document.get("updated_at") else None,
            "revision": document.get("revision", 1),
        }

    def create(self, user_id, title, content, summary="", tags=None, visibility="private"):
        title = title.strip()
        if not title or len(title) > 300:
            raise ValueError("title must contain 1 to 300 characters")
        if visibility not in VALID_VISIBILITIES:
            raise ValueError("visibility must be private or public")
        tags = self._validate_tags(tags or [])
        now = datetime.now(timezone.utc)
        notebook = nbformat.v4.new_notebook(
            metadata={"title": title},
            cells=[nbformat.v4.new_markdown_cell(f"# {title}"),
                   nbformat.v4.new_markdown_cell(content)],
        )
        base_slug = slugify(title)[:80] or "document"
        slug = base_slug
        suffix = 1
        while self.db.notebooks.find_one({"slug": slug}, {"_id": 1}):
            slug, suffix = f"{base_slug}-{suffix}", suffix + 1
        owner_id = ObjectId(user_id) if ObjectId.is_valid(user_id) else user_id
        document = {
            "notebook": notebook, "owner_id": owner_id, "title": title, "slug": slug,
            "summary": summary[:2000], "tags": tags, "visibility": visibility,
            "allowed_user_ids": [], "topic_ids": [], "created_at": now,
            "updated_at": now, "revision": 1, "is_public": visibility == "public",
        }
        result = self.db.notebooks.insert_one(document)
        document["_id"] = result.inserted_id
        self._audit(user_id, "mcp.document.created", result.inserted_id)
        return self._metadata(document)

    def read(self, user_id, document_id, include_content=True):
        if not ObjectId.is_valid(document_id):
            raise ValueError("Invalid document_id")
        document = self.db.notebooks.find_one({
            "$and": [{"_id": ObjectId(document_id)}, self._visible_query(user_id)]
        })
        if not document:
            raise PermissionError("Document not found or not accessible")
        result = self._metadata(document)
        if include_content:
            result["notebook"] = dict(document.get("notebook", {}))
        return result

    def list(self, user_id, query="", limit=20):
        limit = max(1, min(int(limit), 100))
        filters = [self._visible_query(user_id)]
        if query.strip():
            safe = re.escape(query.strip()[:200])
            filters.append({"$or": [
                {"title": {"$regex": safe, "$options": "i"}},
                {"summary": {"$regex": safe, "$options": "i"}},
                {"tags": query.strip().casefold()[:64]},
            ]})
        cursor = self.db.notebooks.find({"$and": filters}).sort("updated_at", -1).limit(limit)
        return [self._metadata(item) for item in cursor]

    def update(self, user_id, document_id, expected_revision, title=None, content=None,
               summary=None, tags=None, visibility=None):
        current = self._owned_document(document_id, user_id)
        changes = {"updated_at": datetime.now(timezone.utc)}
        if title is not None:
            title = title.strip()
            if not title or len(title) > 300:
                raise ValueError("title must contain 1 to 300 characters")
            changes["title"] = title
            changes["notebook.metadata.title"] = title
        if summary is not None:
            changes["summary"] = summary[:2000]
        if tags is not None:
            changes["tags"] = self._validate_tags(tags)
        if visibility is not None:
            if visibility not in VALID_VISIBILITIES:
                raise ValueError("visibility must be private or public")
            changes.update({"visibility": visibility, "is_public": visibility == "public"})
        if content is not None:
            notebook = nbformat.from_dict(current["notebook"])
            if len(notebook.cells) < 2:
                notebook.cells.append(nbformat.v4.new_markdown_cell(content))
            else:
                notebook.cells[1].source = content
            changes["notebook"] = notebook
        updated = self.db.notebooks.find_one_and_update(
            {"_id": current["_id"], "revision": int(expected_revision)},
            {"$set": changes, "$inc": {"revision": 1}},
            return_document=ReturnDocument.AFTER,
        )
        if not updated:
            raise RuntimeError("Revision conflict; read the document and retry with its current revision")
        self._audit(user_id, "mcp.document.updated", current["_id"])
        return self._metadata(updated)

    def delete(self, user_id, document_id, expected_revision):
        current = self._owned_document(document_id, user_id)
        result = self.db.notebooks.delete_one(
            {"_id": current["_id"], "revision": int(expected_revision)}
        )
        if not result.deleted_count:
            raise RuntimeError("Revision conflict; deletion was not performed")
        self._audit(user_id, "mcp.document.deleted", current["_id"])
        return {"deleted": True, "id": document_id}

    @staticmethod
    def _validate_tags(tags):
        if not isinstance(tags, list) or len(tags) > 30:
            raise ValueError("tags must be a list containing at most 30 values")
        return list(dict.fromkeys(str(tag).strip().casefold()[:64] for tag in tags if str(tag).strip()))

    def _audit(self, user_id, event_type, document_id):
        self.db.audit_events.insert_one({
            "occurred_at": datetime.now(timezone.utc), "event_type": event_type,
            "actor_id": ObjectId(user_id), "document_id": document_id,
        })
