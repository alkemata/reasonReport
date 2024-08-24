from flask import Blueprint, render_template, request, redirect, url_for, jsonify, session, flash, abort, current_app
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from .models import authenticate_user, register_user, create_notebook, update_notebook, get_notebook
from pymongo import MongoClient
import nbformat
from nbconvert import HTMLExporter
from .notebooks import create_rr_notebook
from bson import ObjectId

main= Blueprint('main', __name__)

@main.route('/')
def home():
    if 'username' in session:
        return redirect(url_for('main.dashboard'))
    return render_template('login.html')


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
            access_token = create_access_token(identity=username)

                # Redirect to the main page
            response = redirect(url_for('home'))

                # Attach the JWT token to the response headers or JSON
            response.headers['Authorization'] = f"Bearer {access_token}"
            response.set_cookie('token', access_token)

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
            return redirect(url_for('login'))
        else:
            flash(message, 'danger')

    return render_template('register.html')


@main.route('/home')
def dashboard():
    if 'username' in session:
        return render_template('home.html', username=session['username'])
    else:
        flash('You need to login first', 'danger')
        return redirect(url_for('login'))


@main.route('/logout')
def logout():
    session.pop('username', None)
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))


# Route to display a Jupyter notebook
@main.route('/notebook/<notebook_id>')
def notebook(notebook_id):
    with current_app.app_context():
        notebook = notebooks.find_one({'_id': ObjectId(notebook_id)})

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
def create_notebook():
    new_notebook=create_rr_notebook()
    notebook_id=create_notebook(new_notebook)
    return redirect(url_for('main.edit', notebook_id=notebook_id))


@main.route('/edit/<notebook_id>')
@jwt_required()
def edit_notebook(notebook_id):
    # Get the current user's identity (assuming it is the ID)
    user_id = get_jwt_identity()
    
    # Generate the JWT token for further communication
    token = create_access_token(identity=user_id)
    # Set the JWT token as an HttpOnly cookie
    response = render_template('edit.html', notebook_id=notebook_id, user_id=user_id)
    response.set_cookie('token', token, httponly=True, secure=True)

    return response


@main.route('/api/notebooks/<id>', methods=['GET'])
@jwt_required()
def get_api_notebook(id):
    with current_app.app_context():
        current_user = get_jwt_identity()
        
        notebook = notebooks.find_one({"_id": ObjectId(id)})

        if not notebook:
            return jsonify({"msg": "Notebook not found"}), 404

        return notebook, 200
