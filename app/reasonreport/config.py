import os

class Config:
    SECRET_KEY =  'super-secret-key'
    JWT_SECRET_KEY = 'super-secret-jwt-key'
    MONGO_URI = 'mongodb://mongo:27017/flaskdb'
    JWT_TOKEN_LOCATION='cookies'
    JWT_COOKIE_SECURE=False
    JWT_ACCESS_TOKEN_EXPIRES=86400
    JUPYTERLITE_PATH = os.environ.get('JUPYTERLITE_PATH', './_output')
    DEBUG = os.environ.get('FLASK_DEBUG', '').lower() in {'1', 'true', 'yes'}
    CONTENT_SECURITY_POLICY = os.environ.get(
        'CONTENT_SECURITY_POLICY',
        "default-src 'self' data: blob:; "
        "script-src 'self' 'unsafe-eval' 'wasm-unsafe-eval'; "
        "style-src 'self' 'unsafe-inline'; "
        "worker-src 'self' blob:; "
        "connect-src 'self'; "
        "frame-src 'self'; "
        "img-src 'self' data: blob:; "
        "font-src 'self' data:"
    )
