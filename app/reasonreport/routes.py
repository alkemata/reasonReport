from flask import Blueprint, render_template, request, redirect, url_for, jsonify, session, flash
from flask_jwt_extended import create_access_token
from .models import authenticate_user, register_user

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


