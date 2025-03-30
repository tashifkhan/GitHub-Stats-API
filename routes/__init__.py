def register_routes(app):
    """Register all application routes."""
    from .api import api_bp
    from .docs import docs_bp
    
    app.register_blueprint(docs_bp)
    app.register_blueprint(api_bp)
