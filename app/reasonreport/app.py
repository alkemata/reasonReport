# app.py
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory, make_response, flash
from flask_restful import Api, Resource
from config import Config
from models import mongo, get_notebook, get_user_by_username, get_user_by_id, notebook_html, create_notebook, create_user
from resources import (
    CurrentUser, UserLogin, UserLogout, UserRegister, UserResource,
    NotebookCreate, NotebookSave, NotebookQuery, NotebookDelete, authenticate_user
)
from editor_api import (
    EditorNotebookList, EditorNotebookQuery, EditorNotebookRead, EditorSession,
    create_editor_launch
)
from utils import clear_auth_cookie, decode_token, generate_token, set_auth_cookie
from bson.objectid import ObjectId
from flask_debugtoolbar import DebugToolbarExtension
import logging
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from notebooks import create_blank_notebook

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = Config.SECRET_KEY
app.debug = Config.DEBUG
limiter = Limiter(get_remote_address, app=app)

# Initialize PyMongo
mongo.init_app(app)

# Initialize Flask-RESTful API
api = Api(app)
if app.debug:
    toolbar = DebugToolbarExtension(app)
    app.logger.setLevel(logging.DEBUG)


@app.after_request
def add_security_headers(response):
    response.headers['Content-Security-Policy'] = app.config['CONTENT_SECURITY_POLICY']
    return response

# API Routes
api.add_resource(UserRegister, '/api/register')
api.add_resource(UserLogin, '/api/login')
api.add_resource(UserLogout, '/api/logout')
api.add_resource(CurrentUser, '/api/me')
api.add_resource(UserResource, '/api/users/<string:user_id>')
api.add_resource(NotebookCreate, '/api/notebooks/create')
api.add_resource(NotebookSave, '/api/notebooks/save/<string:notebook_id>')
api.add_resource(NotebookQuery, '/api/notebooks/query/<string:notebook_id>')
api.add_resource(NotebookDelete, '/api/notebooks/<string:notebook_id>/delete')
api.add_resource(EditorSession, '/api/editor/session')
api.add_resource(EditorNotebookList, '/api/editor/notebooks')
api.add_resource(EditorNotebookRead, '/api/editor/notebooks/<string:notebook_id>')
api.add_resource(EditorNotebookQuery, '/api/editor/notebooks/query')

# creation of logging file
logging.basicConfig(filename='user_actions.log', level=logging.INFO, format='%(asctime)s - %(message)s')


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
    next_page = request.args.get('next') or url_for('index')
    if not next_page.startswith('/') or next_page.startswith('//'):
        next_page = url_for('index')
    if request.method == 'GET' and get_user_info_from_token()['is_authenticated']:
        return redirect(next_page)
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        token = authenticate_user(username, password)
        if token:
            response = redirect(next_page)
            set_auth_cookie(response, token)
            logging.info(f"User {request.form['username']} logged in")
            return response
        else:
            flash("Invalid credentials, please try again.")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if len(username) < 3 or len(password) < 8:
            return render_template(
                'register.html',
                error_message='Username must be at least 3 characters and password at least 8 characters.'
            ), 400
        
        # Check if user already exists
        if get_user_by_username(username):
            # User exists, render the registration form with an error message
            error_message = "Username already exists. Please choose a different username."
            return render_template('register.html', error_message=error_message)
        
        # Create user and associated notebook
        user_id = create_user(username, password)
        if user_id:
            # Create a notebook and authenticate the new user immediately.
            notebook_id = create_notebook(user_id)
            token = generate_token(user_id)
            response = redirect(url_for('edit_notebook', identifier=notebook_id))
            set_auth_cookie(response, token)
            logging.info(f"User {username} registered and logged in")
            return response
        else:
            return render_template('error.html', error="Failed to create user.")
    else:
        return render_template('register.html')

@app.route('/create')
def create():
    user_info = get_user_info_from_token()
    if not user_info['is_authenticated']:
        return redirect(url_for('login', next=request.path))
    notebook_id = create_notebook(user_info['user_id'])
    editor_nonce = create_editor_launch(user_info['user_id'])
    return render_template('edit.html', notebook_id=notebook_id, editor_nonce=editor_nonce, **user_info)

@app.route('/create_fromtemplate/<slugid>')
def create_fromtemplate(slugid):
    user_info = get_user_info_from_token()
    if not user_info['is_authenticated']:
        return redirect(url_for('login', next=request.path))
    user_id=user_info['user_id']
    notebook={}
    if slugid=="blank":
        notebook_id='-1'
    else:
        notebook = get_notebook(slugid,user_id)
        notebook_id=str(notebook['_id'])
    if 'message' in notebook and notebook['message'] == 'not_authorized':
        flash('You are not authorized to access this notebook.')
        return render_template('error.html', error="Unauthorized access.", is_author=False, **user_info)
    editor_nonce = create_editor_launch(user_id)
    return render_template('edit.html', notebook_id=notebook_id, editor_nonce=editor_nonce, **user_info)


@app.route('/logout', methods=['GET', 'POST'])
def logout():
    user_info = get_user_info_from_token()
    if user_info['is_authenticated']:
        logging.info(f"User {user_info['username']} logged out")
    session.clear()
    response = make_response(redirect(url_for('login')))
    return clear_auth_cookie(response)

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
    user_id=user_info['user_id']
    notebook = get_notebook(id,user_id)

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
    if not user_info['is_authenticated']:
        return redirect(url_for('login', next=request.path))
    editor_nonce = create_editor_launch(user_info['user_id'])
    return render_template(
        'edit.html', notebook_id=identifier, editor_nonce=editor_nonce, **user_info
    )

JUPYTERLITE_PATH = app.config['JUPYTERLITE_PATH']

# Route to serve JupyterLite static files
@app.route('/jupyterlite/<path:filename>')
def serve_jupyterlite_files(filename):
    return send_from_directory(JUPYTERLITE_PATH, filename)

# Route to serve JupyterLite (assuming you have it set up)
@app.route('/jupyterlite/')
def jupyterlite():
    return send_from_directory(JUPYTERLITE_PATH, 'index.html')

#display content of mongodb database
@app.route('/database')
def database_info():
    """
    Displays a list of MongoDB collections (tables) and the IDs of documents in each collection.
    """
    try:
        collections = mongo.db.list_collection_names()
        database_data = {}

        for collection in collections:
            documents = mongo.db[collection].find({}, {"_id": 1})  # Fetch only IDs
            document_ids = [str(doc["_id"]) for doc in documents]  # Convert ObjectId to string
            database_data[collection] = document_ids

        return jsonify(database_data)
    
    except Exception as e:
        return jsonify({"error": str(e)})

# Run the app
if __name__ == '__main__':
    app.run(debug=True)
