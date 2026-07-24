"""Administrative user helpers backed by the active PyMongo models."""

from werkzeug.security import generate_password_hash

from .models import create_user as create_user_record
from .models import USER_ROLES, mongo


def _public_user(user):
    return {
        'id': str(user['_id']),
        'username': user['username'],
        'role': user.get('role', 'user'),
        'status': user.get('status', 'basic'),
        'landing_page': user.get('landing_page'),
    }


def list_users():
    """Return users without exposing password hashes."""
    return [_public_user(user) for user in mongo.db.users.find()]


def create_user(username, password, status='basic', role='user'):
    """Create a user using the same validation and hashing as registration."""
    user_id = create_user_record(
        username,
        password,
        role=role,
        additional_fields={'status': status},
    )
    if not user_id:
        return f"User '{username}' already exists."
    return f"User '{username}' created successfully."


def modify_user(username, new_password=None, new_status=None, new_role=None):
    """Modify password, status, and/or role for an existing user."""
    user = mongo.db.users.find_one({'username': username})
    if not user:
        return f"User '{username}' not found."

    update_fields = {}
    if new_password:
        if len(new_password) < 8:
            raise ValueError('Password must be at least 8 characters')
        update_fields['password'] = generate_password_hash(new_password)
    if new_status:
        update_fields['status'] = new_status
    if new_role:
        if new_role not in USER_ROLES:
            raise ValueError(f"Role must be one of: {', '.join(sorted(USER_ROLES))}")
        update_fields['role'] = new_role

    if not update_fields:
        return f"No updates provided for user '{username}'."
    mongo.db.users.update_one({'_id': user['_id']}, {'$set': update_fields})
    return f"User '{username}' updated successfully."


def delete_user(username):
    """Delete a user and all notebooks authored by that user."""
    user = mongo.db.users.find_one({'username': username})
    if not user:
        return f"User '{username}' not found."
    user_id = str(user['_id'])
    mongo.db.users.delete_one({'_id': user['_id']})
    mongo.db.notebooks.delete_many({'author': user_id})
    return f"User '{username}' deleted successfully."
