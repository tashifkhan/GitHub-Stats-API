from app import create_app
import os

os.environ['FLASK_ENV'] = 'prod'

app = create_app('prod')

if __name__ == "__main__":
    app.run(
        host=app.config.get('HOST', '0.0.0.0'),
        port=app.config.get('PORT', 8989)
    )