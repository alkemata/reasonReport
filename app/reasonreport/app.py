# app.py
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory, make_response, flash
from flask_restful import Api, Resource
from config import Config
from models import mongo, get_notebook, get_user_by_username, get_user_by_id, notebook_html, create_notebook, create_user
from resources import (
    UserRegister, UserResource,
    NotebookCreate, NotebookSave, NotebookQuery, NotebookDelete, authenticate_user
)
from utils import decode_token
from bson.objectid import ObjectId
from flask_debugtoolbar import DebugToolbarExtension
import logging
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from notebooks import create_blank_notebook

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = Config.SECRET_KEY
app.debug = True
limiter = Limiter(get_remote_address, app=app)

# Initialize PyMongo
mongo.init_app(app)

# Initialize Flask-RESTful API
api = Api(app)
toolbar = DebugToolbarExtension(app)
app.logger.setLevel(logging.DEBUG)

# API Routes
api.add_resource(UserRegister, '/api/register')
api.add_resource(UserResource, '/api/users/<string:user_id>')
api.add_resource(NotebookCreate, '/api/notebooks')
api.add_resource(NotebookSave, '/api/notebooks/save/<string:notebook_id>')
api.add_resource(NotebookQuery, '/api/notebooks/query/<string:notebook_id>')
api.add_resource(NotebookDelete, '/api/notebooks/<string:notebook_id>/delete')

# Function to handle token retrieval and user info extraction
def get_user_info_from_token():
    token = request.cookies.get('jwt_token1')
    if token:
        user_id = decode_token(token)
        if user_id:
            user = get_user_by_id(user_id)
            if user:
                return {
                    'user_id': user_id,
                    'username': user['username'],
                    'user': user,
                    'is_authenticated': True
                }
    return {
        'user_id': None,
        'username': None,
        'user': None,
        'is_authenticated': False
    }

# Frontend Routes

@app.route('/')
def index():
    user_info = get_user_info_from_token()

    notebook = None
    is_author = False

    if user_info['is_authenticated']:
        # Attempt to get notebook by user's slug (username)
        notebook = mongo.db.notebooks.find_one({'slug': user_info['username']})
        if notebook:
            notebook['_id'] = str(notebook['_id'])
            is_author = True
            return render_template('index.html', notebook=notebook_html(notebook), id=notebook['_id'],is_author=is_author, **user_info)
        else:
            return render_template('error.html',error="No personal page",is_author=is_author,**user_info)
    return render_template('error.html',error="Not authenticated",is_author=is_author,**user_info)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Authenticate the user here
        token=authenticate_user(request.form['username'], request.form['password'])
        if token:
            # Login successful, redirect to the original page
            next_page = request.args.get('next')
            response=redirect(next_page)
            response.set_cookie(
            key='jwt_token1',
            value=token,
            httponly=True,        # Prevent JavaScript access for security
            secure=True,          # Ensure it's only sent over HTTPS (set to False for local development if needed)
            samesite='Strict',    # Help prevent CSRF attacks
            max_age=3600,         # Expiration time in seconds (optional, can also use `expires`)
            path='/'              # Path for the cookie, default is root
    )
            return response
        else:
            flash("Invalid credentials, please try again.")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Check if user already exists
        if get_user_by_username(username):
            # User exists, render the registration form with an error message
            error_message = "Username already exists. Please choose a different username."
            return render_template('register.html', error_message=error_message)
        
        # Create user and associated notebook
        user_id = create_user(username, password)
        if user_id:
            # Create a new notebook with the title and slug as the username
            notebook_id = create_notebook(user_id)
            notebook = get_notebook(notebook_id,user_id)
            if notebook:
                notebook['_id'] = str(notebook['_id'])
                return render_template('notebook.html', notebook=notebook_html(notebook['notebook']), id=notebook['_id'], is_author=True, username=username, is_authenticated=True)
        else:
            return render_template('error.html', error="Failed to create user.")
    else:
        return render_template('register.html')

@app.route('/create')
def create():
    user_info = get_user_info_from_token()
    notebook_id = create_notebook(user_info['user_id'])
    return render_template('edit.html', notebook_id=notebook_id, **user_info)

@app.route('/create_fromtemplate/<slugid>')
def create_fromtemplate(slugid):
    user_info = get_user_info_from_token()
    user_id=user_info['user_id']
    notebook={}
    if slugid=="blank":
        noteboook=create_blank_notebook()
    else:
        notebook = get_notebook(slugid,user_id)
    if 'message' in notebook and notebook['message'] == 'not_authorized':
        flash('You are not authorized to access this notebook.')
        return render_template('error.html', error="Unauthorized access.", is_author=False, **user_info)
    return render_template('edit.html', notebook_id=notebook_id, **user_info)


@app.route('/logout')
def logout():
    session.clear()  # Clear Flask session cookies
    response = make_response(redirect(url_for('index')))
    # Manually clear all other cookies
    for cookie in request.cookies:
        response.set_cookie(cookie, '', expires=0)   
    return response


@app.route('/slug/<slug>')
def notebook(slug):
    user_info = get_user_info_from_token()
    user_id=user_info['user_id']
    notebook = get_notebook(slug,user_id)    
    is_author = False
    print(user_id)
    if notebook:
        if 'message' in notebook:
            flash('You are not authorized to access this notebook.')
            return render_template('error.html', error=notebook['message'], is_author=False, **user_info)
        notebook['_id'] = str(notebook['_id'])
        if user_info['user_id'] and notebook['author'] == str(user_info['user_id']):
            is_author = True

        # Fetch author's username
        author = get_user_by_id(notebook['author'])
        notebook['author_username'] = author['username'] if author else 'Unknown'

        return render_template('notebook.html', notebook=notebook_html(notebook['notebook']),id=notebook['_id'], is_author=is_author, **user_info)
    else:
        return render_template('error.html', error='Not found', is_author=False, **user_info)

@app.route('/id/<id>')
def notebookid(id):
    user_info = get_user_info_from_token()
    notebook = get_notebook(id)

    is_author = False
    if 'message' in notebook and notebook['message'] == 'not_authorized':
        flash('You are not authorized to access this notebook.')
        return render_template('error.html', error="Unauthorized access.", is_author=False, **user_info)
    if notebook:
        notebook['_id'] = str(notebook['_id'])
        if user_info['user_id'] and notebook['author'] == str(user_info['user_id']):
            is_author = True

        # Fetch author's username
        author = get_user_by_id(notebook['author'])
        notebook['author_username'] = author['username'] if author else 'Unknown'

        return render_template('notebook.html', notebook=notebook_html(notebook['notebook']), id=notebook['_id'],is_author=is_author, **user_info)
    else:
        return render_template('notebook.html', notebook=None, is_author=False, **user_info)

@app.route('/edit/<identifier>')
def edit_notebook(identifier):
    user_info = get_user_info_from_token()
    return render_template('edit.html', notebook_id=identifier, **user_info)

JUPYTERLITE_PATH = './_output'  # Change this to the path where JupyterLite files are stored

# Route to serve JupyterLite static files
@app.route('/jupyterlite/<path:filename>')
def serve_jupyterlite_files(filename):
    return send_from_directory(JUPYTERLITE_PATH, filename)

# Route to serve JupyterLite (assuming you have it set up)
@app.route('/jupyterlite/')
def jupyterlite():
    return send_from_directory(JUPYTERLITE_PATH, 'index.html')

# Run the app
if __name__ == '__main__':
    app.run(debug=True)
