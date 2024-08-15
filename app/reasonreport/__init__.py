from flask import Flask
from flask_jwt_extended import JWTManager
from pymongo import MongoClient
from flask_cors import CORS

jwt = JWTManager()

def create_app(config_filename=None):
    app = Flask(__name__)

    if config_filename:
        app.config.from_pyfile(config_filename)
    
    # Initialize JWT
    jwt.init_app(app)
    
    # Enable CORS
    CORS(app)
    
    # MongoDB client setup
    app.mongo_client = MongoClient(app.config["MONGO_URI"])
    app.db = app.mongo_client['notebooks_db']
    
    # Register Blueprints
    from app.routes import main_blueprint
    from app.api import api_blueprint
    
    app.register_blueprint(main_blueprint)
    app.register_blueprint(api_blueprint, url_prefix="/api")

    return app
