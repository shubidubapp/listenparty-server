from flask import Flask

# noinspection PyUnresolvedReferences
import monkey_patch
from config import config
from extensions import oauth, cache, login_manager, db, cors
from socket_server import sio
from utils import configure_global_logging

configure_global_logging()


def init_app(_app):
    oauth.init_app(_app)
    sio.init_app(
        _app,
        message_queue=f"redis://{_app.config['CACHE_REDIS_HOST']}",
        cors_allowed_origins="*",
        logger=_app.config["DEBUG"],
        engineio_logger=_app.config["DEBUG"]
    )
    cache.init_app(_app)
    login_manager.init_app(_app)
    db.init_app(_app)
    cors.init_app(_app)


def register_blueprints(_app):
    from blueprints.api import blueprint as api_blueprint
    _app.register_blueprint(api_blueprint)

    from blueprints.views import blueprint as views_blueprint
    _app.register_blueprint(views_blueprint)


if __name__ == '__main__':
    print("Creating app.")
    app = Flask(__name__, static_folder="static/", template_folder="templates/")
    print("Reading config.")
    app.config.from_object(config)
    print("init extensions and register blueprints")
    init_app(app)
    register_blueprints(app)
    print(f"starting at: {app.config['APP_HOST']}:{app.config['APP_PORT']}")
    sio.run(app, host=app.config["APP_HOST"], port=app.config['APP_PORT'])
