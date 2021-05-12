from flask import Blueprint, jsonify, url_for, current_app
from flask_login import current_user, login_user, login_required, logout_user
from mongoengine import DoesNotExist
from werkzeug.utils import redirect

from extensions import oauth
from models import User, Token

blueprint = Blueprint("api", __name__, url_prefix="/api")


@blueprint.route('/access_token')
@login_required
def access_token():
    me = oauth.spotify.get("me")
    return jsonify({"access_token": current_user.token.access_token})


@blueprint.route('/test')
@login_required
def test():
    resp = oauth.spotify.get("me").json()
    return jsonify(resp)


@blueprint.route('/auth')
def auth():
    token = oauth.spotify.authorize_access_token()
    resp = oauth.spotify.get("me")
    user_me = resp.json()
    try:
        user = User.objects.get(username=user_me["id"])
    except DoesNotExist:
        user = User()
        user.username = user_me["id"]
        user.token = Token()

    user.token.set_from_dict(token)
    user.save()
    login_user(user, remember=True)
    return redirect(url_for('views.done'))


@blueprint.route('/login')
def login():
    redirect_uri = url_for('api.auth', _external=True, _scheme=current_app.config.get("EXTERNAL_SCHEME", "http"))
    return oauth.spotify.authorize_redirect(redirect_uri, _external=True)


@blueprint.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('views.done'))


@blueprint.route('/logged-in')
def logged_in():
    return jsonify({"loggedIn": current_user.is_authenticated})
