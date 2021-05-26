import re

from bson import ObjectId
from flask import Blueprint, jsonify, url_for, current_app, request
from flask_login import current_user, login_user, login_required, logout_user
from mongoengine import DoesNotExist
from werkzeug.utils import redirect

from extensions import oauth
from models import User, Token, Stream
from utils import prepare_status, message

blueprint = Blueprint("api", __name__, url_prefix="/api")


@blueprint.route('/access_token')
@login_required
def access_token():
    _me = oauth.spotify.get("me")
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
        user.img = user_me["images"][0]["url"]

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
    order_by = request.args.get("order_by", default=None)
    active = str(request.args.get("active", default="true")).lower() in ["true", "yes", "1"]
    try:
        from_ = int(request.args.get("from", default=0))
        amount = int(request.args.get("amount", default=max_page_size))
    except ValueError:
        return

    filter_ = request.args.get("filter", default=None)

    result = stream_list_query(from_, amount, filter_, order_by, active)
    stream_count = result["stream_count"]
    streams = result["streams"]
    user_default_img = url_for(
        'static', filename="user_default.png",
        _external=True, _scheme=current_app.config.get("EXTERNAL_SCHEME", "http")
    )
    return {
        "streams": [
            {
                "name": stream["name"], "listeners_length": stream["listeners_length"],
                "utcdate": stream["date"],
                "streamer": {
                    "name": stream["streamer"][0].get("display_name", stream["streamer"][0]["username"]),
                    "img": stream["streamer"][0].get("img", user_default_img)
                },
                "order_index": from_ + index,
                "pk": stream["_id"].__str__()
            } for index, stream in enumerate(streams)
        ],
        "stream_count": stream_count
    }


@blueprint.route('/listener-list')
@login_required
def listener_list():
    max_page_size = current_app.config.get("MAX_PAGE_SIZE", 20)
    stream_id = request.args.get("stream", default=None)

    if stream_id is None and current_user.stream:
        stream_id = current_user.stream.pk
    elif stream_id is None:
        return {
            "message": message("No stream is specified", "ERROR"),
        }
    try:
        from_ = int(request.args.get("from", default=0))
        amount = int(request.args.get("amount", default=max_page_size))
    except ValueError:
        return

    filter_ = re.escape(request.args.get("filter", default=""))

    user_default_img = url_for(
        'static', filename="user_default.png"
    )
    result = listener_query(stream_id, filter_, from_, amount)
    return {
        "listeners": [
            {
                "name": listener.get("display_name", listener.get("_id")),
                "img": listener.get("img", user_default_img),
                "order_index": from_ + index,
                "pk": listener["_id"].__str__()
            } for index, listener in enumerate(result["listeners"])
        ],
        "listener_count": result["listener_count"]
    }


def stream_list_query(from_, amount, filter_=None, order_by=None, active=None):
    filter_ = filter_ or ""
    order_by = order_by or {"listeners_length": -1}
    active = active if active is not None else True

    pipeline = [
        {"$match": {"$expr": {"$and": [
            {"$regexMatch": {"input": "$name", "regex": f".*{filter_}.*", "options": "i"}},
            {"$eq": ["$active", active]}
        ]}}},
        {"$lookup": {"from": "user", "localField": "streamer", "foreignField": "_id", "as": "streamer"}},
        {"$project": {
            "listeners_length": {"$size": "$listeners"},
            "date": 1,
            "name": 1,
            "active": 1,
            "streamer": 1,
        }},
        {"$sort": {"date": -1, "+name": 1, **order_by}},
        {"$group": {"_id": None, "stream_count": {"$sum": 1}, "streams": {"$push": "$$ROOT"}}},
        {"$project": {
            "stream_count": 1,
            "streams": {"$slice": ["$streams", from_, amount]}
        }}
    ]
    try:
        return Stream.objects().no_cache().aggregate(pipeline).next()
    except StopIteration:
        return {"stream_count": 0, "streams": []}


def listener_query(stream_id, filter_, from_, amount):
    pipeline = [
        {"$match": {"_id": ObjectId(stream_id)}},
        {"$lookup":
            {
                "from": "user",
                "let": {"listeners": "$listeners"},
                "pipeline": [
                    {
                        "$match":
                            {
                                "$expr":
                                    {
                                        "$and":
                                            [
                                                {"$in": ["$_id", "$$listeners"]},
                                                {"$or": [
                                                    {
                                                        "$regexMatch":
                                                            {"input": "$display_name", "regex": f".*{filter_}.*",
                                                             "options": "i"}
                                                    },
                                                    {
                                                        "$regexMatch":
                                                            {"input": "$display_name", "regex": f".*{filter_}.*",
                                                             "options": "i"}
                                                    }
                                                ]}
                                            ]
                                    }
                            }
                    }
                ],
                "as": "listeners"
            }},
        {"$project": {
            "listener_count": {"$size": "$listeners"},
            "listeners": {"$slice": [
                "$listeners",
                from_,
                amount
            ]},
            "_id": 0
        }},
    ]
    try:
        return Stream.objects().no_cache().aggregate(pipeline).next()
    except StopIteration:
        return {
            "listener_count": 0,
            "listeners": []
        }
