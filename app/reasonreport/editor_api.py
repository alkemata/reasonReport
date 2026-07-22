"""Scoped API exposed only to authenticated ReasonReport JupyterLite sessions."""

from datetime import datetime, timedelta, timezone
from functools import wraps
import hashlib
import secrets
from urllib.parse import urlsplit

from bson.objectid import ObjectId
from flask import request
from flask_restful import Resource

from models import mongo
from utils import token_required

SESSION_TTL_SECONDS = 900
LAUNCH_TTL_SECONDS = 60
EDITOR_HEADER = 'X-ReasonReport-Editor'
TOKEN_HEADER = 'X-ReasonReport-Editor-Token'
QUERY_FIELDS = {'_id', 'title', 'slug', 'author', 'is_public'}


def _digest(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def _same_origin_request():
    if request.headers.get(EDITOR_HEADER) != 'jupyterlite':
        return False
    origin = request.headers.get('Origin')
    if not origin:
        return request.headers.get('Sec-Fetch-Site') in {None, 'same-origin'}
    parsed = urlsplit(origin)
    return parsed.scheme in {'http', 'https'} and parsed.netloc == request.host


def create_editor_session(user_id):
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=SESSION_TTL_SECONDS)
    mongo.db.editor_sessions.create_index('delete_at', expireAfterSeconds=0)
    mongo.db.editor_sessions.insert_one({
        'token_digest': _digest(token),
        'user_id': str(user_id),
        'expires_at': expires_at,
        'delete_at': expires_at + timedelta(hours=1),
    })
    return token, expires_at


def create_editor_launch(user_id):
    nonce = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=LAUNCH_TTL_SECONDS)
    mongo.db.editor_launches.create_index('expires_at', expireAfterSeconds=0)
    mongo.db.editor_launches.insert_one({
        'nonce_digest': _digest(nonce),
        'user_id': str(user_id),
        'expires_at': expires_at,
    })
    return nonce


def editor_session_required(function):
    @wraps(function)
    def decorated(*args, **kwargs):
        if not _same_origin_request():
            return {'message': 'JupyterLite editor context required'}, 403
        token = request.headers.get(TOKEN_HEADER, '')
        if not token:
            return {'message': 'Editor session token is missing'}, 401
        session = mongo.db.editor_sessions.find_one({
            'token_digest': _digest(token),
            'user_id': request.user['id'],
            'expires_at': {'$gt': datetime.now(timezone.utc)},
        })
        if not session:
            return {'message': 'Editor session is invalid or expired'}, 401
        return function(*args, **kwargs)
    return decorated


def _access_filter(user_id):
    return {'$or': [{'author': str(user_id)}, {'is_public': True}]}


def _summary(document):
    date = document.get('date')
    return {
        'id': str(document['_id']),
        'title': document.get('title', ''),
        'slug': document.get('slug', ''),
        'author': document.get('author'),
        'date': date.isoformat() if hasattr(date, 'isoformat') else date,
        'is_public': bool(document.get('is_public', False)),
    }


class EditorSession(Resource):
    @token_required
    def post(self):
        if not _same_origin_request():
            return {'message': 'JupyterLite editor context required'}, 403
        payload = request.get_json(silent=True) or {}
        launch_nonce = payload.get('launch_nonce', '')
        launch = mongo.db.editor_launches.find_one_and_delete({
            'nonce_digest': _digest(launch_nonce),
            'user_id': request.user['id'],
            'expires_at': {'$gt': datetime.now(timezone.utc)},
        }) if launch_nonce else None
        renewal_token = request.headers.get(TOKEN_HEADER, '')
        renewal = mongo.db.editor_sessions.find_one({
            'token_digest': _digest(renewal_token),
            'user_id': request.user['id'],
            'expires_at': {'$gt': datetime.now(timezone.utc) - timedelta(hours=1)},
        }) if renewal_token else None
        if not launch and not renewal:
            return {'message': 'Editor launch is invalid or expired'}, 403
        token, expires_at = create_editor_session(request.user['id'])
        return {'editor_token': token, 'expires_at': expires_at.isoformat()}, 201


class EditorNotebookList(Resource):
    @token_required
    @editor_session_required
    def get(self):
        limit = min(max(request.args.get('limit', 50, type=int), 1), 100)
        documents = mongo.db.notebooks.find(_access_filter(request.user['id'])).sort('date', -1).limit(limit)
        return {'documents': [_summary(document) for document in documents]}, 200


class EditorNotebookRead(Resource):
    @token_required
    @editor_session_required
    def get(self, notebook_id):
        if not ObjectId.is_valid(notebook_id):
            return {'message': 'Notebook not found'}, 404
        document = mongo.db.notebooks.find_one({
            '$and': [{'_id': ObjectId(notebook_id)}, _access_filter(request.user['id'])]
        })
        if not document:
            return {'message': 'Notebook not found'}, 404
        result = _summary(document)
        result['notebook'] = document['notebook']
        return {'document': result}, 200


class EditorNotebookQuery(Resource):
    @token_required
    @editor_session_required
    def post(self):
        payload = request.get_json(silent=True) or {}
        filters = payload.get('filters', {})
        if not isinstance(filters, dict) or any(key not in QUERY_FIELDS or key.startswith('$') for key in filters):
            return {'message': 'Unsupported query field'}, 400
        query = {}
        for key, value in filters.items():
            if isinstance(value, (dict, list)):
                return {'message': 'Query operators are not allowed'}, 400
            if key == '_id':
                if not ObjectId.is_valid(str(value)):
                    return {'documents': []}, 200
                value = ObjectId(value)
            query[key] = value
        limit = payload.get('limit', 50)
        if not isinstance(limit, int):
            return {'message': 'Limit must be an integer'}, 400
        limit = min(max(limit, 1), 100)
        documents = mongo.db.notebooks.find({'$and': [query, _access_filter(request.user['id'])]}).sort('date', -1).limit(limit)
        return {'documents': [_summary(document) for document in documents]}, 200
