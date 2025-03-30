import os
from typing import Dict, Any

class Config:
    """Base configuration for the application."""
    DEBUG = False
    TESTING = False
    GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
    PORT = int(os.getenv('PORT', 8989))
    HOST = os.getenv('HOST', '0.0.0.0')

class DevelopmentConfig(Config):
    """Configuration for development environment."""
    DEBUG = True

class ProductionConfig(Config):
    """Configuration for production environment."""
    pass

class TestingConfig(Config):
    """Configuration for testing environment."""
    TESTING = True

config_by_name: Dict[str, Any] = {
    'dev': DevelopmentConfig,
    'prod': ProductionConfig,
    'test': TestingConfig
}

def get_config():
    """Return the appropriate configuration based on environment."""
    env = os.getenv('FLASK_ENV', 'dev')
    return config_by_name.get(env, DevelopmentConfig)
