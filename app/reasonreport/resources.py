# resources.py
from flask_restful import Resource, reqparse
from flask import request, jsonify,  make_response
from models import (
    create_user, get_user_by_username, get_user_by_id, update_user, delete_user,
    create_notebook, save_notebook, get_notebook, delete_notebook
)
from utils import token_required,set_token_cookie
from werkzeug.security import check_password_hash
import json

# User Registration
class UserRegister(Resource):
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('username', required=True, help="Username cannot be blank!")
        parser.add_argument('password', required=True, help="Password cannot be blank!")
        args = parser.parse_args()
        
        try:
            user_id = create_user(args['username'], args['password'])
            print('User created succesfully')
            return {'message': 'User created successfully', 'user_id': user_id}, 201
        except ValueError as e:
            return {'message': str(e)}, 400

# User Login
class UserLogin(Resource):
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('username', required=True, help="Username cannot be blank!")
        parser.add_argument('password', required=True, help="Password cannot be blank!")
        args = parser.parse_args()
        
        user = get_user_by_username(args['username'])
        if not user or not check_password_hash(user['password'], args['password']):
            return {'message': 'Invalid credentials'}, 401
        
        # Generate a response and set the token cookie
        response = {'message': 'Login successful'}
        header=set_token_cookie(response,str(user['_id']))
        return response, 200,  header
        

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
class NotebookCreate(Resource):
    @token_required
    def post(self):
        author_id = request.user['id']
        notebook_id = create_notebook(author_id)
        return {'message': 'Notebook created', 'notebook_id': notebook_id}, 201

class NotebookSave(Resource):
    @token_required
    def put(self, notebook_id):
        parser = reqparse.RequestParser()
        parser.add_argument('notebook', required=True, help="Notebook JSON is required")
        args = parser.parse_args()
        
        notebook = get_notebook(notebook_id) # for checking authour
        if not notebook:
            return {'message': 'Notebook not found'}, 404
        
        if notebook['author'] != request.user['id']:
            return {'message': 'Unauthorized access to this notebook'}, 403
        
        save_notebook(notebook_id, json.loads(args['notebook']))
        return {'message': 'OK'}, 200

class NotebookQuery(Resource):
    @token_required
    def get(self,notebook_id):
                
        if not notebook_id and not slug:
            return {'message': 'Provide either id or slug as query parameter'}, 400
        
        query = notebook_id if notebook_id else slug
        notebook = get_notebook(query)
        
        if not notebook:
            return {'message': 'Notebook not found'}, 404
        #notebook['date']=notebook['date'].isoformat()
        if notebook['author'] != request.user['id']:
            return {'message': 'Unauthorized access to this notebook'}, 403
        
        notebook['_id'] = str(notebook['_id'])
        return {'notebook': notebook['notebook']}, 200

class NotebookDelete(Resource):
    @token_required
    def delete(self, notebook_id):
        notebook = get_notebook(notebook_id)
        if not notebook:
            return {'message': 'Notebook not found'}, 404
        
        if notebook['author'] != request.user['id']:
            return {'message': 'Unauthorized'}, 403
        
        delete_notebook(notebook_id)
        return {'message': 'Notebook deleted successfully'}, 200
