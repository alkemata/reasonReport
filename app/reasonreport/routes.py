from flask import Blueprint, render_template, request, redirect, url_for, jsonify, session, flash, abort, current_app
from flask_jwt_extended import create_access_token
from .models import authenticate_user, register_user
from pymongo import MongoClient
import nbformat
from nbconvert import HTMLExporter

main= Blueprint('main', __name__)

@main.route('/')
def home():
    if 'username' in session:
        return redirect(url_for('dashboard'))
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
            return redirect(url_for('dashboard'))
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


@main.route('/dashboard')
def dashboard():
    if 'username' in session:
        return render_template('dashboard.html', username=session['username'])
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
def show_notebook(notebook_id):
    db=current_app.db
    # Fetch the notebook from the database
    notebook = db.notebooks.find_one({'_id': notebook_id})

    if notebook is None:
        abort(404)  # If notebook not found, return 404 page

    # Assuming your notebook is stored in JSON format under 'content'
    nb_content = notebook.get('content')

    if not nb_content:
        abort(404)  # If notebook content is empty or invalid, return 404 page

    # Load notebook content as a notebook node
    nb_node = nbformat.reads(nb_content, as_version=4)

    # Convert notebook to HTML using nbconvert
    html_exporter = HTMLExporter()
    (body, resources) = html_exporter.from_notebook_node(nb_node)

    # Render the HTML with the title and body of the notebook
    return render_template('notebook.html', title=notebook.get('title'), body=body)



