# utils.py
from functools import wraps
from flask import request, jsonify, session
from models import get_user_by_username, get_user_by_id
from werkzeug.security import check_password_hash
import jwt
from datetime import datetime, timedelta
from config import Config

def generate_token(user_id):
    payload = {
        'user_id': user_id,
        'exp': datetime.utcnow() + timedelta(hours=24)
    }
    token = jwt.encode(payload, Config.SECRET_KEY, algorithm='HS256')
    return token

def decode_token(token):
    try:
        payload = jwt.decode(token, Config.SECRET_KEY, algorithms=['HS256'])
        return payload['user_id']
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        #token = request.headers.get('Authorization', '').replace('Bearer ', '')
        token = request.cookies.get('jwt_token1')
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
            'username': user['username']
        }
        
        return f(*args, **kwargs)
    
    return decorated


