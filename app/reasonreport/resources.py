# resources.py
from flask_restful import Resource, reqparse
from flask import jsonify, make_response, request
from models import (
    create_user, get_user_by_username, get_user_by_id, update_user, delete_user,
    create_notebook_content, create_new_notebook, save_notebook, get_notebook, delete_notebook
)
from utils import clear_auth_cookie, set_auth_cookie, token_required, generate_token
from werkzeug.security import check_password_hash, generate_password_hash
import logging

# User Registration
class UserRegister(Resource):
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('username', required=True, help="Username cannot be blank!")
        parser.add_argument('password', required=True, help="Password cannot be blank!")
        args = parser.parse_args()

        try:
            username = args['username'].strip()
            user_id = create_user(username, args['password'])
            if user_id:
                token = generate_token(user_id)
                response = make_response(jsonify({
                    'message': 'User created successfully',
                    'user': {'id': user_id, 'username': username}
                }), 201)
                set_auth_cookie(response, token)
                logging.info(f"User {username} created successfully")
                return response
            else:
                return {'message': 'Username already exists'}, 400
        except ValueError as e:
            return {'message': str(e)}, 400

# User Login
def authenticate_user(username, password):
    if not username or not password:
        return None
    user = get_user_by_username(username.strip())
    if not user or not check_password_hash(user['password'], password):
        return None

    return generate_token(str(user['_id']))


def public_user(user):
    return {
        'id': str(user['_id']),
        'username': user['username'],
        'landing_page': user.get('landing_page')
    }


class UserLogin(Resource):
    def post(self):
        payload = request.get_json(silent=True) or request.form
        token = authenticate_user(payload.get('username', ''), payload.get('password', ''))
        if not token:
            return {'message': 'Invalid credentials'}, 401
        user = get_user_by_username(payload.get('username', '').strip())
        response = make_response(jsonify({'user': public_user(user)}), 200)
        return set_auth_cookie(response, token)


class UserLogout(Resource):
    def post(self):
        return clear_auth_cookie(make_response(jsonify({'message': 'Logged out'}), 200))


class CurrentUser(Resource):
    @token_required
    def get(self):
        user = get_user_by_id(request.user['id'])
        return {'user': public_user(user)}, 200

        

# User CRUD Operations
class UserResource(Resource):
    @token_required
    def get(self, user_id):
        user = get_user_by_id(user_id)
        if not user:
            return {'message': 'User not found'}, 404
        if request.user['id'] != user_id:
            return {'message': 'Unauthorized'}, 403
        return {'user': public_user(user)}, 200
    
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
            username = args['username'].strip()
            if len(username) < 3:
                return {'message': 'Username must be at least 3 characters'}, 400
            existing = get_user_by_username(username)
            if existing and str(existing['_id']) != user_id:
                return {'message': 'Username already exists'}, 409
            update_fields['username'] = username
        if args['password']:
            if len(args['password']) < 8:
                return {'message': 'Password must be at least 8 characters'}, 400
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
        if not delete_user(user_id):
            return {'message': 'User not found'}, 404
        response = make_response(jsonify({'message': 'User deleted successfully'}), 200)
        return clear_auth_cookie(response)

# Notebook Operations
class NotebookCreate(Resource): #todo add logic to validate the notebook
    @token_required
    def post(self):
        author_id = request.user['id']
        payload = request.get_json(silent=True) or {}
        try:
            notebook_id, slug = create_new_notebook(
                author_id, request.user['username'], payload
            )
        except (ValueError, TypeError) as error:
            return {'message': str(error)}, 400
        return {
            'message': 'Notebook created',
            'notebook_id': notebook_id,
            'slug': slug,
        }, 201

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
            slug = save_notebook(
                notebook_id, request.user['id'], request.user['username'], payload
            )
        except (ValueError, TypeError) as error:
            return {'message': str(error)}, 400
        if not slug:
            return {'message': 'Notebook not found'}, 404
        return {'message': 'OK', 'notebook_id': notebook_id, 'slug': slug}, 200

class NotebookQuery(Resource):
    @token_required
    def get(self,notebook_id):
                
        user_id=request.user['id']
        if notebook_id == '-1':
            return {
                'notebook': create_notebook_content(
                    user_id, request.user['username']
                )
            }, 200
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
