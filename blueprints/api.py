from flask import Blueprint, jsonify, url_for, current_app, request
from flask_login import current_user, login_user, login_required, logout_user
from mongoengine import DoesNotExist
from werkzeug.utils import redirect
from mongoengine.queryset.visitor import Q

from extensions import oauth
from models import User, Token, Stream
from utils import prepare_status

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

    user.display_name = user_me["display_name"]
    if len(user_me["images"]) > 0:
        user.img = user_me["images"]["url"]

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


@blueprint.route('/status')
def status():
    return {"status": prepare_status()}


@blueprint.route('/stream-list')
@login_required
def stream_list():
    max_page_size = current_app.config.get("MAX_PAGE_SIZE", 20)
    order_by = request.args.get("order_by", default="-listeners_length")
    active = str(request.args.get("active", default="true")).lower() in ["true", "yes", "1"]
    try:
        from_ = int(request.args.get("from", default=0))
        amount = int(request.args.get("amount", default=max_page_size))
        to = min(int(request.args.get("to", default=from_ + amount)), from_ + max_page_size)
    except ValueError:
        return

    filter_ = request.args.get("filter", default=None)
    q = Q(active=active)
    if filter_ and len(filter_) >= 5:
        q = q & Q(name__icontains=filter_)

    streams = Stream.objects(q).order_by(order_by, "-date")[from_:to].select_related(1)
    stream_count = Stream.objects(q).count()
    user_default_img = url_for(
        'static', filename="user_default.png",
        _external=True, _scheme=current_app.config.get("EXTERNAL_SCHEME", "http")
    )
    return {
        "streams": [
            {
                "name": stream.name, "listeners_length": stream.listeners_length,
                "utcdate": stream.date,
                "streamer": {
                    "name": stream.streamer.display_name if stream.streamer.display_name else stream.streamer.username,
                    "img": stream.streamer.img if stream.streamer.img else user_default_img
                },
                "order_index": from_ + index,
                "pk": stream.pk.__repr__()
            } for index, stream in enumerate(streams)
        ],
        "stream_count": stream_count
    }
