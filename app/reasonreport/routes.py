from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from flask_jwt_extended import create_access_token

main_blueprint = Blueprint('main', __name__)

# User authentication info (in-memory for simplicity)
users = {
    "admin": {"password": "admin", "role": "admin"},
    "user123": {"password": "user123", "role": "user"},
    "guest": {"password": "guest", "role": "guest"}
}

@main_blueprint.route('/')
def home():
    return render_template('home.html')

@main_blueprint.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = users.get(username)

        if user and user['password'] == password:
            access_token = create_access_token(identity={"username": username, "role": user['role']})
            return jsonify({"access_token": access_token}), 200

        return jsonify({"msg": "Invalid username or password"}), 401

    return render_template('login.html')

from flask import Flask, render_template, request, redirect, url_for, session, flash
from config import Config
from models import register_user, authenticate_user
from flask_pymongo import PyMongo

app = Flask(__name__)
app.config.from_object(Config)
mongo = PyMongo(app)


@app.route('/')
def home():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')


@app.route('/login', methods=['GET', 'POST'])
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


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        invitation_code = request.form['invitation_code']

        success, message = register_user(username, password, invitation_code)
        if success:
            flash(message, 'success')
            return redirect(url_for('login'))
        else:
            flash(message, 'danger')

    return render_template('register.html')


@app.route('/dashboard')
def dashboard():
    if 'username' in session:
        return render_template('dashboard.html', username=session['username'])
    else:
        flash('You need to login first', 'danger')
        return redirect(url_for('login'))


@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)
