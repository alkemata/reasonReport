from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from bson import ObjectId

api_blueprint = Blueprint('api', __name__)

@api_blueprint.route('/notebooks', methods=['GET'])
@jwt_required(locations=['cookies'])
def get_notebooks():
    current_user = get_jwt_identity()
    db = request.app.db
    role = current_user.get("role")

    if role not in ["admin", "user"]:
        return jsonify({"msg": "Permission denied"}), 403

    notebooks = db.notebooks.find()
    result = []
    for notebook in notebooks:
        notebook['_id'] = str(notebook['_id'])
        result.append(notebook)

    return jsonify(result), 200

@api_blueprint.route('/notebooks', methods=['POST'])
@jwt_required(locations=['cookies'])
def create_notebook():
    current_user = get_jwt_identity()
    role = current_user.get("role")

    if role != "admin":
        return jsonify({"msg": "Permission denied"}), 403

    notebook_data = request.json
    db = request.app.db
    result = db.notebooks.insert_one(notebook_data)
    
    return jsonify({"msg": "Notebook created", "id": str(result.inserted_id)}), 201

@api_blueprint.route('/notebooks/<notebook_id>', methods=['PUT'])
@jwt_required(locations=['cookies'])
def update_notebook(notebook_id):
    current_user = get_jwt_identity()
    role = current_user.get("role")

    if role != "admin":
        return jsonify({"msg": "Permission denied"}), 403

    notebook_data = request.json
    db = request.app.db
    db.notebooks.update_one({"_id": ObjectId(notebook_id)}, {"$set": notebook_data})
    
    return jsonify({"msg": "Notebook updated"}), 200

@api_blueprint.route('/notebooks/<notebook_id>', methods=['DELETE'])
@jwt_required(locations=['cookies'])
def delete_notebook(notebook_id):
    current_user = get_jwt_identity()
    role = current_user.get("role")

    if role != "admin":
        return jsonify({"msg": "Permission denied"}), 403

    db = request.app.db
    db.notebooks.delete_one({"_id": ObjectId(notebook_id)})
    
    return jsonify({"msg": "Notebook deleted"}), 200
