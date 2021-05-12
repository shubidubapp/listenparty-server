from authlib.integrations.flask_client import OAuth
from flask_caching import Cache
from flask_cors import CORS
from flask_login import LoginManager, current_user
from flask_mongoengine import MongoEngine

login_manager = LoginManager()
oauth = OAuth()
db = MongoEngine()
cache = Cache()
cors = CORS()

login_manager.login_view = "api.login"


def fetch_token():
    if current_user.is_authenticated:
        token = current_user.token.to_token()
        return token
    return None


def update_token(token, **_):
    current_user.token.access_token = token["access_token"]
    current_user.token.refresh_token = token["refresh_token"]
    current_user.token.expires_at = token["expires_at"]
    current_user.save()


scope_list = [
    "user-read-playback-state",
    "user-read-currently-playing",
    "user-modify-playback-state",
]
scope = " ".join(scope_list)

oauth.register(
    name='spotify',
    api_base_url='https://api.spotify.com/v1/',
    access_token_url='https://accounts.spotify.com/api/token',
    authorize_url='https://accounts.spotify.com/authorize',
    authorize_params={"scope": scope},
    fetch_token=fetch_token,
    update_token=update_token,
    refresh_token_url='https://accounts.spotify.com/api/token',
    refresh_token_params={'grant_type': 'refresh_token'}
)
