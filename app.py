import eventlet
eventlet.monkey_patch()

from flask import Flask

from extensions import oauth, cache, login_manager, db, cors
from socket_server import sio
from utils import configure_global_logging

configure_global_logging()

app = Flask(__name__, static_folder="static/", template_folder="templates/")
app.config.from_pyfile('config.py')


def init_app():
    print("init_app")
    oauth.init_app(app)
    sio.init_app(app, message_queue='redis://', cors_allowed_origins="*")
    cache.init_app(app)
    login_manager.init_app(app)
    db.init_app(app)
    cors.init_app(app)


def register_blueprints():
    from blueprints.api import blueprint as api_blueprint
    app.register_blueprint(api_blueprint)

    from blueprints.views import blueprint as views_blueprint
    app.register_blueprint(views_blueprint)


init_app()
register_blueprints()
sio.run(app)
