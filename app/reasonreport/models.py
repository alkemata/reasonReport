from flask_bcrypt import Bcrypt
from pymongo import MongoClient
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from bson.objectid import ObjectId
import datetime

bcrypt = Bcrypt()

client = MongoClient('mongodb://mongo:27017/flaskdb')
db = client.flaskdb
users_collection = db.users
notebooks_collection = db.notebooks


def register_user(username, password):
    # Check if username is already taken
    existing_user = users_collection.find_one({"username": username})
    if existing_user:
        print('existing username')
        return False, "Username already exists"

    # Hash the password and create the user with default status as 'basic'
    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
    users_collection.insert_one({
        "username": username,
        "password": hashed_password,
        "role": "basic",  # Default status for newly registered users
        "notebook":0,
        "status":"waiting"
    })

    return True, "User registered successfully"


def check_admin(username):
    user=get_user_by_username(username)
    projection = {"role": 1, "_id": 0}
    
    # Find the user and retrieve the 'role'
    user = users_collection.find_one(query, projection)
    if user.get('role')=="admin":
        return True
    return False
    user=get_user_by_username(username)

def set_admin(username):
    query = {"username": username}
    update = {"$set": {"role": "admin"}}
    result = users_collection.update_one(query, update)
    return

def authenticate_user(username, password):
    # Find the user in the database
    user = users_collection.find_one({"username": username})
    if user and bcrypt.check_password_hash(user['password'], password):
        return True, user
    return False, None


def get_user_by_username(username):
    return users_collection.find_one({"username": username})

def create_notebook(data):
    try:
        result = db.notebooks.insert_one(data)
        return {'id': str(result.inserted_id)}, 201
    except Exception as e:
        return {'error': str(e)}, 500

def update_notebook(id, data):
    try:
        result = mongo.db.notebooks.update_one({'_id': ObjectId(id)}, {"$set": data})
        if result.matched_count:
            return {'msg': 'Notebook updated'}, 200
        else:
            return {'msg': 'Notebook not found'}, 404
    except Exception as e:
        return {'error': str(e)}, 500

def get_notebook(id):
    try:
        notebook = mongo.db.notebooks.find_one({'_id': ObjectId(id)})
        if notebook:
            return dumps(notebook), 200
        else:
            return {'msg': 'Notebook not found'}, 404
    except Exception as e:
        return {'error': str(e)}, 500

def delete_notebook(id):
    try:
        result = mongo.db.notebooks.delete_one({'_id': ObjectId(id)})
        if result.deleted_count:
            return {'msg': 'Notebook deleted'}, 200
        else:
            return {'msg': 'Notebook not found'}, 404
    except Exception as e:
        return {'error': str(e)}, 500