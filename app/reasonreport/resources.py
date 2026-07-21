# resources.py
from flask_restful import Resource, reqparse
from flask import request
from models import (
    create_user, get_user_by_username, get_user_by_id, update_user, delete_user,
    create_notebook_content, create_new_notebook, save_notebook, get_notebook, delete_notebook
)
from utils import token_required,generate_token
from werkzeug.security import check_password_hash
import logging

# User Registration
class UserRegister(Resource):
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('username', required=True, help="Username cannot be blank!")
        parser.add_argument('password', required=True, help="Password cannot be blank!")
        args = parser.parse_args()

        try:
            user_id = create_user(args['username'], args['password'])
            if user_id:
                logging.info(f"User {args['username']} created successfully")
                return {'message': 'User created successfully', 'user_id': user_id}, 201
            else:
                return {'message': 'Username already exists'}, 400
        except ValueError as e:
            return {'message': str(e)}, 400

# User Login
def authenticate_user(username, password):
        
        user = get_user_by_username(username)
        if not user or not check_password_hash(user['password'], password):
            return None

        token = generate_token(str(user['_id']))
        return token

        

# User CRUD Operations
class UserResource(Resource):
    @token_required
    def get(self, user_id):
        user = get_user_by_id(user_id)
        if not user:
            return {'message': 'User not found'}, 404
        user['_id'] = str(user['_id'])
        return {'user': user}, 200
    
    @token_required
    def put(self, user_id):
        if request.user['id'] != user_id:
            return {'message': 'Unauthorized'}, 403
        
        parser = reqparse.RequestParser()
        parser.add_argument('username')
        parser.add_argument('password')
        # Add more fields as needed
        args = parser.parse_args()
        
        update_fields = {}
        if args['username']:
            update_fields['username'] = args['username']
        if args['password']:
            from werkzeug.security import generate_password_hash
            update_fields['password'] = generate_password_hash(args['password'])
        
        if update_fields:
            update_user(user_id, update_fields)
            return {'message': 'User updated successfully'}, 200
        else:
            return {'message': 'No fields to update'}, 400
    
    @token_required
    def delete(self, user_id):
        if request.user['id'] != user_id:
            return {'message': 'Unauthorized'}, 403
        delete_user(user_id)
        return {'message': 'User deleted successfully'}, 200

# Notebook Operations
class NotebookCreate(Resource): #todo add logic to validate the notebook
    @token_required
    def post(self):
        author_id = request.user['id']
        payload = request.get_json(silent=True) or {}
        try:
            notebook_id = create_new_notebook(author_id, payload)
        except (ValueError, TypeError) as error:
            return {'message': str(error)}, 400
        return {'message': 'Notebook created', 'notebook_id': notebook_id}, 201

class NotebookSave(Resource):
    @token_required
    def put(self, notebook_id):
        payload = request.get_json(silent=True) or {}
        notebook = get_notebook(notebook_id, request.user['id'])
        if not notebook or notebook.get('message') == 'not found':
            return {'message': 'Notebook not found'}, 404
        if notebook.get('message') == 'not_authorized':
            return {'message': 'Unauthorized access to this notebook'}, 403
        if notebook['author'] != request.user['id']:
            return {'message': 'Unauthorized access to this notebook'}, 403
        try:
            result = save_notebook(notebook_id, request.user['id'], payload)
        except (ValueError, TypeError) as error:
            return {'message': str(error)}, 400
        if result != 'ok':
            return {'message': 'Notebook not found'}, 404
        return {'message': 'OK', 'notebook_id': notebook_id}, 200

class NotebookQuery(Resource):
    @token_required
    def get(self,notebook_id):
                
        user_id=request.user['id']
        if notebook_id == '-1':
            return {'notebook': create_notebook_content(user_id)}, 200
        else:
            notebook = get_notebook(notebook_id,user_id)
        
        if not notebook or notebook.get('message') == 'not found':
            return {'message': 'Notebook not found'}, 404
        if notebook.get('message') == 'not_authorized':
            return {'message': 'Unauthorized access to this notebook'}, 403
        #notebook['date']=notebook['date'].isoformat()
        if notebook['author'] != request.user['id']:
            return {'message': 'Unauthorized access to this notebook'}, 403
        
        notebook['_id'] = str(notebook['_id'])
        return {'notebook': notebook['notebook']}, 200

class NotebookDelete(Resource):
    @token_required
    def delete(self, notebook_id):
        notebook = get_notebook(notebook_id, request.user['id'])
        if not notebook or notebook.get('message') == 'not found':
            return {'message': 'Notebook not found'}, 404
        if notebook.get('message') == 'not_authorized':
            return {'message': 'Unauthorized'}, 403
        if notebook['author'] != request.user['id']:
            return {'message': 'Unauthorized'}, 403
        
        delete_notebook(notebook_id)
        return {'message': 'Notebook deleted successfully'}, 200
