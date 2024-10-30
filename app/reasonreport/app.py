# app.py
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory, make_response
from flask_restful import Api, Resource
from config import Config
from models import mongo, get_notebook, get_user_by_username, get_user_by_id, notebook_html
from resources import (
    UserRegister, UserResource,
    NotebookCreate, NotebookSave, NotebookQuery, NotebookDelete
)
from utils import decode_token
from bson.objectid import ObjectId
from flask_debugtoolbar import DebugToolbarExtension
import logging

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = Config.SECRET_KEY
app.debug = True

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
    token = request.cookies.get('jwt_token') or session.get('token')
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
            return render_template('index.html', notebook=notebook_html(notebook), is_author=is_author, **user_info)
        else:
            return render_template('error.html',error="Notebook not found",is_author=is_author,**user_info)
    return render_template('error.html',error="No personnal page",is_author=is_author,**user_info)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Authenticate the user here
        if authenticate_user(request.form['username'], request.form['password']):
            # Login successful, redirect to the original page
            next_page = request.args.get('next')

            response.set_cookie(
            key='jwt_token',
            value=token,
            httponly=True,        # Prevent JavaScript access for security
            secure=True,          # Ensure it's only sent over HTTPS (set to False for local development if needed)
            samesite='Strict',    # Help prevent CSRF attacks
            max_age=3600,         # Expiration time in seconds (optional, can also use `expires`)
            path='/'              # Path for the cookie, default is root
    )
            return redirect(next_page or url_for('home'))
        else:
            flash("Invalid credentials, please try again.")
    return render_template('login.html')

@app.route('/register')
def register():
    return render_template('register.html')

@app.route('/slug/<slug>')
def notebook(slug):
    user_info = get_user_info_from_token()
    notebook = get_notebook(slug)

    is_author = False
    if notebook:
        notebook['_id'] = str(notebook['_id'])
        if user_info['user_id'] and notebook['author'] == str(user_info['user_id']):
            is_author = True

        # Fetch author's username
        author = get_user_by_id(notebook['author'])
        notebook['author_username'] = author['username'] if author else 'Unknown'

        return render_template('notebook.html', notebook=notebook_html(notebook['notebook']), is_author=is_author, **user_info)
    else:
        return render_template('notebook.html', notebook=None, is_author=False, **user_info)

@app.route('/id/<id>')
def notebookid(id):
    user_info = get_user_info_from_token()
    notebook = get_notebook(id)

    is_author = False
    if notebook:
        notebook['_id'] = str(notebook['_id'])
        if user_info['user_id'] and notebook['author'] == str(user_info['user_id']):
            is_author = True

        # Fetch author's username
        author = get_user_by_id(notebook['author'])
        notebook['author_username'] = author['username'] if author else 'Unknown'

        return render_template('notebook.html', notebook=notebook_html(notebook['notebook']), is_author=is_author, **user_info)
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
