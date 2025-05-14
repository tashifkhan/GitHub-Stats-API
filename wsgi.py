from gevent import monkey
monkey.patch_all()                          # <— patch stdlib for cooperative IO

import os
from app import create_app

os.environ['FLASK_ENV'] = 'prod'
app = create_app('prod')

if __name__ == "__main__":
    from gevent.pywsgi import WSGIServer    # <— use Gevent’s WSGI server
    host = app.config.get('HOST', '0.0.0.0')
    port = app.config.get('PORT', 8989)
    http_server = WSGIServer((host, port), app)
    http_server.serve_forever()