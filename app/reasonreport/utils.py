# utils.py
from functools import wraps
from flask import current_app, request
from models import get_user_by_id
import jwt
from datetime import datetime, timedelta, timezone
from config import Config

def generate_token(user_id):
    now = datetime.now(timezone.utc)
    payload = {
        'sub': str(user_id),
        'iat': now,
        'exp': now + timedelta(seconds=Config.JWT_ACCESS_TOKEN_EXPIRES)
    }
    token = jwt.encode(payload, Config.JWT_SECRET_KEY, algorithm='HS256')
    return token

def decode_token(token):
    try:
        payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=['HS256'])
        return payload.get('sub') or payload.get('user_id')
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        authorization = request.headers.get('Authorization', '')
        bearer_token = authorization[7:].strip() if authorization.startswith('Bearer ') else None
        token = request.cookies.get('jwt_token1') or bearer_token
        if not token:
            return {'message': 'Token is missing!'}, 401
        
        user_id = decode_token(token)
        if not user_id:
            return {'message': 'Token is invalid or expired!'}, 401
        
        user = get_user_by_id(user_id)
        if not user:
            return {'message': 'User not found!'}, 401
        
        # Attach user info to the request
        request.user = {
            'id': str(user['_id']),
            'username': user['username'],
            'role': user.get(
                'role',
                'admin' if user['username'] == current_app.config['ADMIN_USERNAME'] else 'user',
            ),
        }
        
        return f(*args, **kwargs)
    
    return decorated


def set_auth_cookie(response, token):
    response.set_cookie(
        key='jwt_token1',
        value=token,
        httponly=True,
        secure=current_app.config['JWT_COOKIE_SECURE'],
        samesite='Strict',
        max_age=current_app.config['JWT_ACCESS_TOKEN_EXPIRES'],
        path='/'
    )
    return response


def clear_auth_cookie(response):
    response.delete_cookie(
        key='jwt_token1',
        path='/',
        secure=current_app.config['JWT_COOKIE_SECURE'],
        httponly=True,
        samesite='Strict'
    )
    return response


