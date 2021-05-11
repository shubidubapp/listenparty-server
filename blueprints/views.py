import os

from authlib.integrations.base_client import OAuthError
from flask import render_template, url_for, Blueprint, redirect, send_from_directory, current_app
from flask_login import logout_user, login_required

from extensions import oauth

blueprint = Blueprint("views", __name__, url_prefix="/i", template_folder="templates/", static_folder="static/")


@blueprint.errorhandler(OAuthError)
def handle_error(error):
    return render_template('error.html', error=error)


@blueprint.route('/done')
def done():
    return render_template('done.html')


@blueprint.route('/login')
def login():
    redirect_uri = url_for('api.auth', _external=True)
    return oauth.spotify.authorize_redirect(redirect_uri, _external=True)


@blueprint.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('views.done'))


@blueprint.route('/', defaults={'path': ''})
@blueprint.route('/<path:path>')
def homepage(path):
    if path != "" and os.path.exists(current_app.template_folder + '/' + path):
        return send_from_directory(current_app.template_folder, path)
    return send_from_directory(current_app.template_folder, 'index.html')

