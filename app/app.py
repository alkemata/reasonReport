from flask import Flask, jsonify, request
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from pymongo import MongoClient
from flask_cors import CORS
from bson import ObjectId

app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = "super-secret"  # Change this!

jwt = JWTManager(app)
CORS(app)

# Setup MongoDB Client
client = MongoClient("mongodb://localhost:27017/")
db = client['notebooks_db']
notebooks_collection = db['notebooks']

# User roles
USER_ROLES = {
    "admin": ["read", "write", "delete"],
    "user": ["read"],
    "guest": ["read"]
}

# Authenticated user information (for example purposes)
users = {
    "admin": {"password": "admin", "role": "admin"},
    "user123": {"password": "user123", "role": "user"},
    "guest": {"password": "guest", "role": "guest"}
}

# User Authentication Route
@app.route("/login", methods=["POST"])
def login():
    username = request.json.get("username", None)
    password = request.json.get("password", None)
    
    user = users.get(username)
    
    if user and user['password'] == password:
        access_token = create_access_token(identity={"username": username, "role": user['role']})
        return jsonify(access_token=access_token), 200

    return jsonify({"msg": "Bad username or password"}), 401

# JWT Protected Route: Create Notebook
@app.route("/notebooks", methods=["POST"])
@jwt_required()
def create_notebook():
    current_user = get_jwt_identity()
    role = current_user.get("role")

    if "write" not in USER_ROLES.get(role, []):
        return jsonify({"msg": "Permission denied"}), 403

    notebook_data = request.json
    result = notebooks_collection.insert_one(notebook_data)
    return jsonify({"msg": "Notebook created", "id": str(result.inserted_id)}), 201

# JWT Protected Route: Get All Notebooks
@app.route("/notebooks", methods=["GET"])
@jwt_required()
def get_notebooks():
    current_user = get_jwt_identity()
    role = current_user.get("role")

    if "read" not in USER_ROLES.get(role, []):
        return jsonify({"msg": "Permission denied"}), 403

    notebooks = notebooks_collection.find()
    result = []
    for notebook in notebooks:
        notebook['_id'] = str(notebook['_id'])  # Convert ObjectId to string
        result.append(notebook)

    return jsonify(result), 200

# JWT Protected Route: Update Notebook
@app.route("/notebooks/<notebook_id>", methods=["PUT"])
@jwt_required()
def update_notebook(notebook_id):
    current_user = get_jwt_identity()
    role = current_user.get("role")

    if "write" not in USER_ROLES.get(role, []):
        return jsonify({"msg": "Permission denied"}), 403

    notebook_data = request.json
    notebooks_collection.update_one({"_id": ObjectId(notebook_id)}, {"$set": notebook_data})
    return jsonify({"msg": "Notebook updated"}), 200

# JWT Protected Route: Delete Notebook
@app.route("/notebooks/<notebook_id>", methods=["DELETE"])
@jwt_required()
def delete_notebook(notebook_id):
    current_user = get_jwt_identity()
    role = current_user.get("role")

    if "delete" not in USER_ROLES.get(role, []):
        return jsonify({"msg": "Permission denied"}), 403

    notebooks_collection.delete_one({"_id": ObjectId(notebook_id)})
    return jsonify({"msg": "Notebook deleted"}), 200

if __name__ == '__main__':
    app.run(debug=True)
