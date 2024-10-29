# app.py
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory, make_response
from flask_restful import Api
from config import Config
from models import mongo, get_notebook, get_user_by_username, get_user_by_id, notebook_html
from resources import (
    UserRegister, UserLogin, UserResource,
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
api.add_resource(UserLogin, '/api/login')
api.add_resource(UserResource, '/api/users/<string:user_id>')
api.add_resource(NotebookCreate, '/api/notebooks')
api.add_resource(NotebookSave, '/api/notebooks/save/<string:notebook_id>')
api.add_resource(NotebookQuery, '/api/notebooks/query/<string:notebook_id>')
api.add_resource(NotebookDelete, '/api/notebooks/<string:notebook_id>/delete')

# Frontend Routes

@app.route('/')
def index():
    token = request.cookies.get('token') or session.get('token')
    is_authenticated = False
    if token:
        user_id = decode_token(token)
        is_authenticated=True
        if user_id:
            user = get_user_by_id(user_id)
            if user:
                # Attempt to get notebook by user's slug (username)
                notebook = mongo.db.notebooks.find_one({'slug': user['username']})
                if notebook:
                    notebook['_id'] = str(notebook['_id'])
                    is_author = True
                else:
                    notebook = None
                    is_author = False
                return render_template('index.html', notebook=notebook_html(notebook), user=user,is_author=is_author,is_authenticated=is_authenticated)
    return render_template('index.html', notebook=None, is_author=False)

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/register')
def register():
    return render_template('register.html')

@app.route('/slug/<slug>')
def notebook(slug):
    token = request.cookies.get('jwt_token') 
    user_id = None
    is_authenticated=False
    if token:
        user_id = decode_token(token)
        is_authenticated=True
    notebook = get_notebook(slug)
    if notebook:
        notebook['_id'] = str(notebook['_id'])
        is_author = False
        app.logger.info(is_author)
        app.logger.info(user_id)
        app.logger.info(notebook['author'] )
        if user_id and notebook['author'] == str(user_id):
            is_author = True
        # Fetch author's username
        author = get_user_by_id(notebook['author'])
        if author:
            notebook['author_username'] = author['username']
        else:
            notebook['author_username'] = 'Unknown'
        return render_template('notebook.html', notebook=notebook_html(notebook['notebook']), is_author=is_author, id=slug,is_authenticated=is_authenticated)
    else:
        return render_template('notebook.html', notebook=None, is_author=False, id=slug)

@app.route('/id/<id>')
def notebookid(id):
    token = request.cookies.get('jwt_token') 
    user_id = None
    is_authenticated=False
    if token:
        user_id = decode_token(token)
        is_authenticated=True
    notebook = get_notebook(id)
    if notebook:
        slug = notebook.get('slug')
        #if slug:
         #   try:
         #       response = make_response(redirect(f'https://rr.alkemata.com/slug/{slug}'))
                # Set an authentication cookie
              #  if token:
               #     response.set_cookie('jwt_token', value=str(token), httponly=True, secure=True, samesite='Strict')
                #return response  # Ensure response is returned
          #  except Exception as e:
           #     app.logger.error(f"Redirection failed: {e}")

        notebook['_id'] = str(notebook['_id'])
        is_author = False
        if user_id and notebook['author'] == str(user_id):
            is_author = True
        # Fetch author's username
        author = get_user_by_id(notebook['author'])
        if author:
            notebook['author_username'] = author['username']
        else:
            notebook['author_username'] = 'Unknown'
        return render_template('notebook.html', notebook=notebook_html(notebook['notebook']), is_author=is_author, id=id,is_authenticated=is_authenticated)
    else:
        return render_template('notebook.html', notebook=None, is_author=False, id=id)

@app.route('/edit/<identifier>')
def edit_notebook(identifier):
    token = request.cookies.get('jwt_token') 
    user_id = None
    is_authenticated=False
    if token:
        user_id = decode_token(token)
        is_authenticated=True
    # This route serves the JupyterLite editor
    return render_template('edit.html', notebook_id=identifier,is_authenticated=is_authenticated,user_id=user_id)

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
