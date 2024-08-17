from flask import current_app
from models import bcrypt, users_collection

def list_users():
    """List all users in the database."""
    with current_app.app_context():
        users = users_collection.find()
        return list(users)

def create_user(username, password, status='basic'):
    """Create a new user with a given username, password, and status."""
    with current_app.app_context():
        existing_user = users_collection.find_one({"username": username})
        if existing_user:
            return f"User '{username}' already exists."

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        users_collection.insert_one({
            "username": username,
            "password": hashed_password,
            "status": status
        })
        return f"User '{username}' created successfully."

def modify_user(username, new_password=None, new_status=None):
    """Modify a user's password and/or status."""
    with current_app.app_context():
        user = users_collection.find_one({"username": username})
        if not user:
            return f"User '{username}' not found."

        update_fields = {}
        if new_password:
            hashed_password = bcrypt.generate_password_hash(new_password).decode('utf-8')
            update_fields["password"] = hashed_password
        if new_status:
            update_fields["status"] = new_status

        if update_fields:
            users_collection.update_one({"username": username}, {"$set": update_fields})
            return f"User '{username}' updated successfully."
        else:
            return f"No updates provided for user '{username}'."

def delete_user(username):
    """Delete a user from the database."""
    with current_app.app_context():
        result = users_collection.delete_one({"username": username})
        if result.deleted_count == 0:
            return f"User '{username}' not found."
        return f"User '{username}' deleted successfully."