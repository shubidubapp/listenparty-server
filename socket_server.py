import functools

from flask import request, current_app
from flask_login import current_user
from flask_socketio import SocketIO, disconnect, leave_room, rooms, join_room
from mongoengine import DoesNotExist, Q
from pydantic import ValidationError

import utils
from extensions import cache, oauth
from models import Stream, User, ChatQueue, ChatDJ, ChatMessage
from schemas import AddDJSchema, AddQueueSchema, MessageSchema, ErrorSchema
from utils import prepare_status, message, ACTIVITY

sio = SocketIO()


def user_key(user=None):
    if user:
        return f"user::{user.username}"
    return f"user::{current_user.id}"


def stream_room_key(name):
    return f"music__{name}"


def get_stream(stream_name, check_active=False) -> Stream:
    if check_active:
        return Stream.objects.get(name=stream_name, active=True)
    else:
        return Stream.objects.get(name=stream_name)


def authenticated_only(f):
    @functools.wraps(f)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            disconnect()
        else:
            return f(*args, **kwargs)

    return wrapped


@sio.on('connect')
def connect():
    prev = cache.get(user_key())
    if prev:
        disconnect(prev)
    cache.set(user_key(), request.sid)


@sio.on('disconnect')
def disconnect_():
    cache.delete(user_key())
    return stop()


@sio.on_error()
def error_handler(e):
    current_app.logger.exception(e)


@sio.on("stop")
@authenticated_only
def stop():
    stream = current_user.stream
    if current_user.activity == ACTIVITY.LISTEN:
        current_app.logger.debug(f"User: {current_user} stopped listening.")
        current_user.stream = None
        current_user.activity = ACTIVITY.NONE
        current_user.save()
        leave_rooms()

        stream.update(pull__listeners=current_user.pk)
        sio.emit("listener_left", to=stream_room_key(stream.name))

        return {
            "message": message("Listening is stopped", "ERROR"),
            "status": prepare_status()
        }
    elif current_user.activity == ACTIVITY.STREAM:
        stream: Stream = current_user.stream
        current_app.logger.debug(f"User: {current_user} stopped streaming.")
        sio.emit("stream_stopped", to=stream_room_key(stream.name),
                 data={"message": message("Streamer stopped.", "ERROR"),
                       "status": prepare_status()},
                 skip_sid=request.sid)
        for listener in stream.listeners:
            sid = cache.get(user_key(listener))
            leave_rooms(sid)
        User.objects(stream=stream).update(set__activity=ACTIVITY.NONE, unset__stream=None)
        stream.update(set__active=False)
        leave_rooms()
        current_user.reload()

        return {
            "message": message("Stream is stopped", "ERROR"),
            "status": prepare_status()
        }


@sio.on("start_stream")
@authenticated_only
def start_stream(data):
    data["stream_name"] = data["stream_name"].strip()
    if not utils.Validator.stream_name_re.match(data["stream_name"]):
        return {
            "message": message("Stream name must be between 5-20 characters and "
                               "should have alphabet, digits, underscore, dash or space characters", "ERROR"),
            "status": prepare_status()
        }
    try:
        stream: Stream = get_stream(data["stream_name"], check_active=True)
        if stream and stream.streamer.id != current_user.id:
            return {
                "message": message("Stream name already has an active streamer.", "ERROR"),
                "status": prepare_status()
            }
    except DoesNotExist:
        stream = Stream()
        stream.streamer = current_user.to_dbref()
        stream.name = data["stream_name"]

    current_user.activity = ACTIVITY.STREAM
    current_user.stream = stream

    add_to_room(stream_room_key(stream.name), request.sid)

    stream.save()
    current_user.save()
    current_app.logger.debug(f"User: {current_user.id} streaming, '{stream.name}'.")

    return {
        "message": message(f"Started streaming at {stream.name} as {stream.streamer.username}.", "OK"),
        "status": prepare_status()
    }


@sio.on("listen_stream")
@authenticated_only
def listen_stream(data):
    data["stream_name"] = data["stream_name"].strip()
    if not utils.Validator.stream_name_re(data["stream_name"]):
        return {
            "message": message("Stream name must be between 5-20 characters and "
                               "should have alphabet, digits, underscore, dash or space characters", "ERROR"),
            "status": prepare_status()
        }

    if current_user.activity == ACTIVITY.STREAM:
        return {
            "message": message("You can't start listening before streaming.", "ERROR"),
            "status": prepare_status()
        }

    if current_user.activity == ACTIVITY.LISTEN:
        return {
            "message": message("You can't start listening before leaving previous.", "ERROR"),
            "status": prepare_status()
        }

    try:
        stream: Stream = get_stream(data["stream_name"], check_active=True)
    except DoesNotExist:
        return {
            "message": message("This is not an active stream", "ERROR"),
            "status": prepare_status()
        }

    stream.update(push__listeners=current_user.to_dbref())
    current_user.activity = ACTIVITY.LISTEN
    current_user.stream = stream
    add_to_room(stream_room_key(stream.name), request.sid)
    current_user.save()
    current_app.logger.debug(f"User: {current_user} started listening '{stream.name}'.")

    return {
        "message": message(f"Started listening at {stream.name} as {current_user.username}.", "OK"),
        "status": prepare_status()
    }


@sio.on("streamer_update")
@authenticated_only
def streamer_update(data):
    if current_user.activity == ACTIVITY.STREAM and data.get("stream_data", None):
        current_app.logger.debug(
            f"Stream update for '{current_user.stream.name}', {len(current_user.stream.listeners)} listeners.")
        sio.emit("listener_update",
                 data={"stream_data": data["stream_data"]},
                 to=stream_room_key(current_user.stream.name),
                 skip_sid=request.sid)
        return {
            "status": prepare_status()
        }


@sio.on("dj_add")
@authenticated_only
def dj_add(data):
    try:
        schema = AddDJSchema(**data, sender=current_user.display_name)
    except ValidationError as e:
        schema = ErrorSchema(errors=e.errors())
        sio.emit("chat_action", data=schema.dict(exclude_none=True))
        return

    if not (current_user == current_user.stream.streamer or current_user in current_user.stream.dj):
        schema = ErrorSchema(message="You dont have the permission for that")
        sio.emit("chat_action", data=schema.dict(exclude_none=True))
        return
    try:
        new_dj: User = User.objects(Q(username=schema.who) | Q(display_name=schema.who)).get()
    except DoesNotExist:
        schema = ErrorSchema(message=f"User, '{schema.who}', doesn't exist.")
        sio.emit("chat_action", data=schema.dict(exclude_none=True))
        return

    if new_dj not in current_user.stream.dj and new_dj != current_user.stream.streamer:
        current_user.stream.update(push__dj=new_dj)
        model = ChatDJ()
        model.sender = current_user
        model.stream = current_user.stream
        model.date = schema.date
        model.who = schema.who
        model.save()

        sio.emit("chat_action",
                 data={**schema.dict(), "sender": current_user.display_name},
                 to=stream_room_key(current_user.stream.name))
    else:
        schema = ErrorSchema(message=f"User, '{schema.who}', is already a DJ.")
        sio.emit("chat_action", data=schema.dict(exclude_none=True))
        return


@sio.on("queue_add")
@authenticated_only
def queue_add(data):
    try:
        schema = AddQueueSchema(**data, sender=current_user.display_name)
    except ValidationError as e:
        schema = ErrorSchema(errors=e.errors())
        sio.emit("chat_action", data=schema.dict(exclude_none=True))
        return

    if not (current_user == current_user.stream.streamer or current_user in current_user.stream.dj):
        schema = ErrorSchema(message="You dont have the permission for that")
        sio.emit("chat_action", data=schema.dict(exclude_none=True))
        return

    resp = oauth.spotify.get(f"tracks/{schema.track}")
    if resp.status_code != 200:
        schema = ErrorSchema(message="Invalid track")
        sio.emit("chat_action", data=schema.dict(exclude_none=True))
        return

    model = ChatQueue()
    model.sender = current_user
    model.stream = current_user.stream
    model.date = schema.date
    model.track = schema.track
    model.save()
    key = cache.get(user_key())

    stream_name = current_user.stream.name

    def callback(data_):
        if data_["status"] == "ok":
            sio.emit("chat_action",
                     data=schema.dict(exclude_none=True),
                     to=stream_room_key(stream_name), include_self=True)

    sio.emit("add_queue", to=key, data={"track": schema.track}, include_self=True,
             callback=callback)

    return {}


@sio.on("text_message")
@authenticated_only
def text_message(data):
    try:
        schema = MessageSchema(**data, sender=current_user.display_name)
    except ValidationError as e:
        schema = ErrorSchema(errors=e.errors())
        sio.emit("chat_action", data=schema.dict(exclude_none=True))
        return

    model = ChatMessage()
    model.sender = current_user
    model.stream = current_user.stream
    model.date = schema.date
    model.message = schema.message
    model.save()

    sio.emit("chat_action",
             data={**schema.dict(), "sender": current_user.display_name},
             to=stream_room_key(current_user.stream.name), include_self=True)


@sio.on("status")
def status():
    return {"status": prepare_status()}


def leave_rooms(sid=None):
    # user should be in max 1 room.
    for room in rooms(sid=sid):
        if room != sid:
            leave_room(room)


def add_to_room(room_name, sid=None):
    leave_rooms(sid=sid)
    print(room_name)
    join_room(room=room_name, sid=sid)
