from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
import os

from routes import register_routes
from config import get_config

def create_app(config_name=None):
    """Initialize and configure the Flask application."""
    load_dotenv()
    
    app = Flask(__name__)
    CORS(app)
    
    if not config_name:
        config_name = os.getenv('FLASK_ENV', 'dev')
    config = get_config()
    app.config.from_object(config)
    
    register_routes(app)
    
    return app

if __name__ == "__main__":
    app = create_app()
    app.run(
        host=app.config.get('HOST', '0.0.0.0'),
        port=app.config.get('PORT', 8989),
        debug=app.config.get('DEBUG', False)
    )