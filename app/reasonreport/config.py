import os


PYODIDE_CDN = "https://cdn.jsdelivr.net"


def allow_pyodide(policy):
    """Add the sources required by the Pyodide worker to a CSP string."""
    directives = []
    for raw_directive in policy.split(';'):
        parts = raw_directive.split()
        if parts:
            directives.append(parts)

    by_name = {parts[0]: parts for parts in directives}
    for name in ('script-src', 'connect-src'):
        parts = by_name.get(name)
        if parts is None:
            parts = [name, "'self'"]
            directives.append(parts)
            by_name[name] = parts
        if PYODIDE_CDN not in parts:
            parts.append(PYODIDE_CDN)

    return '; '.join(' '.join(parts) for parts in directives) + ';'


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'development-flask-key-change-me-32')
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'development-jwt-key-change-me-32')
    MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://mongo:27017/flaskdb')
    JWT_TOKEN_LOCATION='cookies'
    JWT_COOKIE_SECURE = os.environ.get('JWT_COOKIE_SECURE', 'true').lower() in {'1', 'true', 'yes'}
    JWT_ACCESS_TOKEN_EXPIRES = int(os.environ.get('JWT_ACCESS_TOKEN_EXPIRES', '86400'))
    JUPYTERLITE_PATH = os.environ.get('JUPYTERLITE_PATH', './_output')
    DEBUG = os.environ.get('FLASK_DEBUG', '').lower() in {'1', 'true', 'yes'}
    CONTENT_SECURITY_POLICY = allow_pyodide(os.environ.get(
        'CONTENT_SECURITY_POLICY',
        "default-src 'self' data: blob:; "
        "script-src 'self' 'unsafe-eval' 'wasm-unsafe-eval'; "
        "style-src 'self' 'unsafe-inline'; "
        "worker-src 'self' blob:; "
        "connect-src 'self'; "
        "frame-src 'self'; "
        "img-src 'self' data: blob:; "
        "font-src 'self' data:"
    ))
