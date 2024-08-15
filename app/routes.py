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
