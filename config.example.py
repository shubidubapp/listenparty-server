import os


class Config(object):
    def __init__(self):
        for k in self.__dir__():
            if not k.startswith("_") and k.isupper() and k in os.environ:
                setattr(self, k, os.getenv(k))

    APP_HOST = "127.0.0.1"
    APP_PORT = 5000
    SECRET_KEY = b'secret'

    SPOTIFY_CLIENT_ID = ''
    SPOTIFY_CLIENT_SECRET = ''

    MONGODB_DB = 'listenParty'
    MONGODB_HOST = "127.0.0.1"
    # MONGODB_USERNAME = "listenParty-mongo"
    # MONGODB_PASSWORD = "listenParty-mongo-password"

    CACHE_TYPE = "redis"
    CACHE_KEY_PREFIX = "listenParty_"
    CACHE_REDIS_HOST = "127.0.0.1"

    CORS_SUPPORTS_CREDENTIALS = True
    CORS_ALLOW_ORIGIN = "*"
    EXTERNAL_SCHEME = "http"

    MAX_PAGE_SIZE = 50


class ProductionConfig(Config):
    SECRET_KEY = b'extra_secret'
    MONGODB_HOST = "mongo"
    CACHE_REDIS_HOST = "redis"
    APP_HOST = "0.0.0.0"
    APP_PORT = 5000
    EXTERNAL_SCHEME = "https"


flask_env = os.getenv("FLASK_ENV", default="production")

if flask_env.lower() == "production":
    config = ProductionConfig()
else:
    config = Config()
