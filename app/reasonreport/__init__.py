from flask import Flask
from flask_jwt_extended import JWTManager
from pymongo import MongoClient
from flask_cors import CORS
import os

jwt = JWTManager()

def create_app(config_filename=None):
    app = Flask(__name__)

    # Initialize JWT
    jwt.init_app(app)
    
    # Enable CORS
    CORS(app)

    # Default config file path
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config.py')
    
    # Load the default configuration if the config file exists
    if os.path.exists(config_path):
        app.config.from_pyfile(config_path)
    else:
        # Optionally, you can log a warning or raise an exception if config file is missing
        app.logger.warning('Config file not found, using default settings')

    if config_filename:
        app.config.from_pyfile(config_filename)
    

    # MongoDB client setup
    app.mongo_client = MongoClient(app.config["MONGO_URI"])
    app.db = app.mongo_client['notebooks_db']
    
    # Register Blueprints
    from app.routes import main_blueprint
    from app.api import api_blueprint
    
    app.register_blueprint(main_blueprint)
    app.register_blueprint(api_blueprint, url_prefix="/api")

    return app
