from flask import Blueprint, render_template, request, redirect, url_for, jsonify, session, flash, abort, current_app, send_from_directory
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, set_access_cookies
from .models import authenticate_user, register_user, create_notebook, update_notebook, get_notebook
from pymongo import MongoClient
import nbformat
from nbconvert import HTMLExporter
from .notebooks import create_rr_notebook
from bson import ObjectId

main= Blueprint('main', __name__)

def admin_required(f):
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role != 'admin':
            return jsonify({"error": "Admin access required"}), 403
        return f(*args, **kwargs)
    return decorated_function

# Decorator to check for a valid JWT token
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].split(" ")[1]  # Extract Bearer token
        if not token:
            return jsonify({'message': 'Token is missing!'}), 403
        try:
            # Decode the token to get user data
            data = jwt.decode(token, JWT_SECRET_KEY, algorithms=["HS256"])
            current_user = data['username']
            user_role = data['role']
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired!'}), 403
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Invalid token!'}), 403

        return f(current_user, user_role, *args, **kwargs)
    return decorated

# Decorator to ensure that the user has admin role
def admin_required(f):
    @wraps(f)
    @token_required
    def decorated(current_user, user_role, *args, **kwargs):
        if user_role != 'admin':
            return jsonify({'message': 'Admin access required'}), 403
        return f(current_user, *args, **kwargs)
    return decorated

# Admin route for managing users
@app.route('/admin/users', methods=['GET', 'POST', 'PUT', 'DELETE'])
@admin_required
def manage_users(current_user):
    users_collection = mongo.db.users

    # List users
    if request.method == 'GET':
        users = list(users_collection.find({}, {"password": 0}))  # Exclude passwords
        return jsonify(users)

    # Accept registration (manual addition of users)
    if request.method == 'POST':
        user_data = request.json
        users_collection.insert_one({
            "username": user_data['username'],
            "email": user_data['email'],
            "status": "accepted"
        })
        return jsonify({"message": "User registration accepted"}), 201

    # Edit user
    if request.method == 'PUT':
        user_id = request.json.get('id')
        updated_data = request.json.get('data')
        users_collection.update_one({'_id': user_id}, {'$set': updated_data})
        return jsonify({"message": "User updated"}), 200

    # Delete user
    if request.method == 'DELETE':
        user_id = request.json.get('id')
        users_collection.delete_one({'_id': user_id})
        return jsonify({"message": "User deleted"}), 200
        

@main.route('/')
def home():
    if 'username' in session:
        return redirect(url_for('main.dashboard'))
    return render_template('login.html')

# ==================== routes users.

@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        success, user = authenticate_user(username, password)
        if success:
            session['username'] = user['username']
            flash('Login successful', 'success')
                # Generate the JWT token
            
            access_token = create_access_token(identity=user['username'])

                # Redirect to the main page
            response = redirect(url_for('main.create_notebook_page'))
            set_access_cookies(response, access_token)
            return response

        else:
            flash('Invalid credentials', 'danger')

    return render_template('login.html')


@main.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        success, message = register_user(username, password)
        if success:
            flash(message, 'success')
            return redirect(url_for('main.login'))
        else:
            flash(message, 'danger')

    return render_template('register.html')


@main.route('/home')
def dashboard():
    if 'username' in session:
        return render_template('home.html', username=session['username'])
    else:
        flash('You need to login first', 'danger')
        return redirect(url_for('main.login'))


@main.route('/logout')
def logout():
    session.pop('username', None)
    flash('You have been logged out', 'info')
    return redirect(url_for('main.login'))


# ===================== routes notebook

# Route to display a Jupyter notebook
@main.route('/notebook/<notebook_id>')
def notebook(notebook_id):
    with current_app.app_context():
        notebook = app.db.notebooks.find_one({'_id': ObjectId(notebook_id)})

        # If no notebook is found, display a message
        if notebook is None:
            # If the notebook doesn't exist, show a message
            body = "No notebook with this ID exists yet. You can create one."
            is_author = False  # Assuming they can't be an author of a non-existent notebook
        else:
            # If a notebook exists, process its content
            nb_content = notebook.get('content')
            nb_node = nbformat.reads(nb_content, as_version=4)
            html_exporter = HTMLExporter()
            body, _ = html_exporter.from_notebook_node(nb_node)

            # Check if the current user is the author
            is_author = notebook.get('author_id') == current_user.get_id()

            username=''
            if 'username' in session:
                username=session['username']

        # Render the template with the notebook content or the message
        return render_template('notebook.html', 
                            body=body, 
                            is_author=is_author, 
                            notebook_id=notebook_id, 
                            user_name=username)

@main.route('/create')
def create_notebook_page():
    new_notebook=create_rr_notebook()
    notebook_id=create_notebook(new_notebook)
    return redirect(url_for('main.edit_notebook', notebook_id=notebook_id[0]['id']))


@main.route('/edit/<notebook_id>')
def edit_notebook(notebook_id):
    # Get the current user's identity (assuming it is the ID)
   # if 'username' in session:
    # Set the JWT token as an HttpOnly cookie
    response = render_template('edit.html', title="Edit notebook",is_author=True,notebook_id=notebook_id, user_name=session['username'])
    return response


@main.route('/api/notebooks/<id>', methods=['GET'])
@jwt_required(locations=['cookies'])
def get_api_notebook(id):
    with current_app.app_context():

        notebook = current_app.db.notebooks.find_one({"_id": ObjectId(id)})
        print('=========',notebook)
        if not notebook:
            return jsonify({"msg": "Notebook not found"}), 404
        notebook['_id'] = str(notebook['_id']) 
        return jsonify(notebook), 200

#============= routes Jupyterlite

JUPYTERLITE_PATH = './_output'  # Change this to the path where JupyterLite files are stored

# Route to serve JupyterLite static files
@main.route('/jupyterlite/<path:filename>')
def serve_jupyterlite_files(filename):
    return send_from_directory(JUPYTERLITE_PATH, filename)

# Route for serving the base of JupyterLite (index.html)
@main.route('/jupyterlite/')
def serve_jupyterlite_index():
    return send_from_directory(JUPYTERLITE_PATH, 'index.html')



