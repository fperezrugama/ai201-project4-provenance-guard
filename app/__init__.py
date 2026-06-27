from flask import Flask
import os
from dotenv import load_dotenv

load_dotenv()

def create_app():
    """Application factory pattern"""
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-key-for-testing')

    # Register blueprints
    from app.routes import submit
    app.register_blueprint(submit.bp)
    
    return app