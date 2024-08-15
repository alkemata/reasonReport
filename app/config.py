import os

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'super-secret-key')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'super-secret-jwt-key')
    MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/notebooks_db')
